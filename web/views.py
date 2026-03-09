import logging
from functools import wraps

from flask import (Blueprint, render_template, abort, redirect, request,
                   session, jsonify)

from util import (
    get_authorization_url, get_https_redirect_call_back_url,
    set_access_token, update_session_with_current_user,
    get_dashboard_summary, fetch_expenses, aggregate_monthly,
    aggregate_categories, get_friends_with_balances,
    get_groups_with_balances, get_my_share, _parse_date,
)

views = Blueprint("views", __name__)
logging.basicConfig(level=logging.INFO)


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "access_token" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@views.route("/login")
def login():
    session.clear()  # Clear old session data to ensure a fresh, small Set-Cookie header
    url = get_authorization_url(get_https_redirect_call_back_url(request.root_url))
    return redirect(url)

@views.route("/callback")
def callback():
    if session.get("state") != request.args.get("state"):
        # If the state mismatches (usually from browser caching or back-button), silently restart the login flow
        return redirect("/login")
        
    set_access_token(request.args["code"],
                     get_https_redirect_call_back_url(request.root_url))
    return redirect("/")


@views.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@views.route("/")
def home():
    if "access_token" not in session:
        return render_template("welcome.html")
    update_session_with_current_user()
    return render_template("home.html")


@views.route("/monthly")
@login_required
def monthly():
    update_session_with_current_user()
    return render_template("monthly.html")


@views.route("/categories")
@login_required
def categories():
    update_session_with_current_user()
    return render_template("categories.html")


@views.route("/groups")
@login_required
def groups():
    update_session_with_current_user()
    return render_template("groups.html")


@views.route("/groups/<int:group_id>")
@login_required
def group_detail(group_id):
    update_session_with_current_user()
    return render_template("group_detail.html", group_id=group_id)


@views.route("/friends")
@login_required
def friends():
    update_session_with_current_user()
    return render_template("friends.html")


@views.route("/trends")
@login_required
def trends():
    update_session_with_current_user()
    return render_template("trends.html")


# ---------------------------------------------------------------------------
# JSON API routes
# ---------------------------------------------------------------------------

@views.route("/api/dashboard")
@login_required
def api_dashboard():
    return jsonify(get_dashboard_summary())


@views.route("/api/monthly-spending")
@login_required
def api_monthly_spending():
    months = request.args.get("months", 12, type=int)
    expenses = fetch_expenses(months=months)
    monthly = aggregate_monthly(expenses)
    # Sort months chronologically
    sorted_months = sorted(monthly.keys())
    # Collect all unique categories
    all_cats = set()
    for cats in monthly.values():
        all_cats.update(cats.keys())
    all_cats = sorted(all_cats)

    datasets = {}
    for cat in all_cats:
        datasets[cat] = [round(monthly.get(m, {}).get(cat, 0), 2)
                         for m in sorted_months]

    return jsonify({
        "labels": sorted_months,
        "datasets": datasets,
        "currency": session.get("default_currency", "USD"),
    })


@views.route("/api/category-breakdown")
@login_required
def api_category_breakdown():
    months = request.args.get("months", 12, type=int)
    expenses = fetch_expenses(months=months)
    cats = aggregate_categories(expenses)
    sorted_cats = sorted(cats.items(), key=lambda x: x[1], reverse=True)
    return jsonify({
        "labels": [c[0] for c in sorted_cats],
        "values": [round(c[1], 2) for c in sorted_cats],
        "currency": session.get("default_currency", "USD"),
    })


@views.route("/api/groups")
@login_required
def api_groups():
    return jsonify(get_groups_with_balances())


@views.route("/api/group/<int:group_id>/expenses")
@login_required
def api_group_expenses(group_id):
    expenses = fetch_expenses(months=12, group_id=group_id)
    currency = session.get("default_currency", "USD")
    result = []
    for e in expenses:
        result.append({
            "id": e.getId(),
            "description": e.getDescription(),
            "cost": float(e.getCost()),
            "my_share": get_my_share(e.getUsers()),
            "currency": e.getCurrencyCode(),
            "date": e.getDate(),
            "category": e.getCategory().getName() if e.getCategory() else "Uncategorized",
        })
    result.sort(key=lambda x: x["date"], reverse=True)
    return jsonify({"expenses": result, "currency": currency})


@views.route("/api/friends")
@login_required
def api_friends():
    return jsonify(get_friends_with_balances())


@views.route("/api/trends")
@login_required
def api_trends():
    months = request.args.get("months", 12, type=int)
    expenses = fetch_expenses(months=months)
    monthly = aggregate_monthly(expenses)
    sorted_months = sorted(monthly.keys())
    totals = [round(sum(monthly[m].values()), 2) for m in sorted_months]
    return jsonify({
        "labels": sorted_months,
        "totals": totals,
        "currency": session.get("default_currency", "USD"),
    })
