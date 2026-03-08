import os
from datetime import datetime
from collections import defaultdict

from dotenv import load_dotenv
from flask import session
from splitwise import Splitwise

load_dotenv()


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

def get_splitwise_client():
    """Return a Splitwise client — authenticated if access_token is present."""
    key = os.getenv("CONSUMER_KEY")
    secret = os.getenv("CONSUMER_SECRET")
    if "access_token" in session:
        return Splitwise(consumer_key=key, consumer_secret=secret,
                         api_key=session["access_token"])
    return Splitwise(consumer_key=key, consumer_secret=secret)


def get_authorization_url(redirect_uri):
    client = get_splitwise_client()
    url, state = client.getOAuth2AuthorizeURL(redirect_uri)
    session["state"] = state
    return url


def set_access_token(code, redirect_uri):
    client = get_splitwise_client()
    access_token = client.getOAuth2AccessToken(code, redirect_uri)["access_token"]
    session["access_token"] = access_token


def get_https_redirect_call_back_url(root_url):
    return root_url + "callback"


def update_session_with_current_user():
    """Fetch current user info and cache in session."""
    if "user_id" in session:
        return
    client = get_splitwise_client()
    user = client.getCurrentUser()
    session["user_id"] = user.getId()
    session["first_name"] = user.getFirstName()
    session["last_name"] = user.getLastName() or ""
    session["email"] = user.getEmail() or ""
    session["default_currency"] = user.getDefaultCurrency()
    pic = user.getPicture()
    session["avatar_url"] = pic.getMedium() if pic else ""


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _parse_date(date_str):
    """Parse Splitwise date string."""
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return datetime.now()


def get_my_share(users):
    """Return the current user's owed share from expense users list."""
    uid = session.get("user_id")
    for u in users:
        if u.getId() == uid:
            return float(u.getOwedShare())
    return 0.0


def fetch_expenses(months=12, group_id=None):
    """Fetch expenses from the API, filtered and cleaned."""
    from dateutil.relativedelta import relativedelta
    from datetime import date

    client = get_splitwise_client()
    update_session_with_current_user()

    start_date = date.today() - relativedelta(months=months)
    kwargs = dict(dated_after=str(start_date), limit=999999, visible=True)
    if group_id:
        kwargs["group_id"] = group_id
    else:
        kwargs["friend_id"] = session["user_id"]

    expenses = client.getExpenses(**kwargs)

    # Filter out payments and debt consolidations
    filtered = []
    for e in expenses:
        if e.getPayment():
            continue
        if e.getCreationMethod() == "debt_consolidation":
            continue
        filtered.append(e)
    return filtered


def aggregate_monthly(expenses):
    """Return {month_str: {category: cost}}."""
    result = defaultdict(lambda: defaultdict(float))
    currency = session.get("default_currency", "USD")
    for e in expenses:
        if e.getCurrencyCode() != currency:
            continue
        dt = _parse_date(e.getDate())
        month = dt.strftime("%Y-%m")
        cat = e.getCategory().getName() if e.getCategory() else "Uncategorized"
        cost = get_my_share(e.getUsers())
        result[month][cat] += cost
    return dict(result)


def aggregate_categories(expenses):
    """Return {category: total_cost}."""
    result = defaultdict(float)
    currency = session.get("default_currency", "USD")
    for e in expenses:
        if e.getCurrencyCode() != currency:
            continue
        cat = e.getCategory().getName() if e.getCategory() else "Uncategorized"
        cost = get_my_share(e.getUsers())
        result[cat] += cost
    return dict(result)


def get_dashboard_summary():
    """Return summary stats for the dashboard."""
    client = get_splitwise_client()
    update_session_with_current_user()

    friends = client.getFriends()
    groups = client.getGroups()

    total_owed_to_me = 0.0
    total_i_owe = 0.0
    for friend in friends:
        for balance in friend.getBalances():
            amt = float(balance.getAmount())
            if amt > 0:
                total_owed_to_me += amt
            else:
                total_i_owe += abs(amt)

    return {
        "you_owe": round(total_i_owe, 2),
        "you_are_owed": round(total_owed_to_me, 2),
        "groups_count": len(groups),
        "friends_count": len(friends),
        "currency": session.get("default_currency", "USD"),
        "user_name": session.get("first_name", "User"),
    }


def get_friends_with_balances():
    """Return list of friends with their balances."""
    client = get_splitwise_client()
    friends = client.getFriends()
    result = []
    for f in friends:
        balances = []
        for b in f.getBalances():
            balances.append({
                "currency": b.getCurrencyCode(),
                "amount": float(b.getAmount()),
            })
        pic = f.getPicture()
        result.append({
            "id": f.getId(),
            "name": f.getFirstName() + " " + (f.getLastName() or ""),
            "avatar": pic.getMedium() if pic else "",
            "balances": balances,
        })
    return result


def get_groups_with_balances():
    """Return list of groups with simplified balances."""
    client = get_splitwise_client()
    groups = client.getGroups()
    uid = session.get("user_id")
    result = []
    for g in groups:
        try:
            if g.getId() == 0:
                continue  # skip non-group expenses
            members = []
            my_balance = 0.0
            currency = session.get("default_currency", "USD")
            for m in g.getMembers():
                try:
                    for b in m.getBalances():
                        if m.getId() == uid:
                            my_balance += float(b.getAmount())
                except Exception:
                    pass
                members.append({
                    "id": m.getId(),
                    "name": (m.getFirstName() or "") + " " + (m.getLastName() or ""),
                })
            cover_url = ""
            try:
                cover = g.getCoverPhoto()
                if cover:
                    cover_url = cover.getXLarge() or ""
            except Exception:
                pass
            result.append({
                "id": g.getId(),
                "name": g.getName() or "Unnamed Group",
                "cover": cover_url,
                "members": members,
                "my_balance": round(my_balance, 2),
                "currency": currency,
            })
        except Exception:
            continue
    return result
