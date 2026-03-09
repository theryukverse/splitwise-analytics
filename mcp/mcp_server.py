import os
import json
from collections import defaultdict
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from splitwise import Splitwise
from splitwise.expense import Expense
from mcp.server.fastmcp import FastMCP
from starlette.responses import HTMLResponse, PlainTextResponse
from starlette.requests import Request

# Load credentials from .env
ENV_FILE = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_FILE)

CACHE_FILE = Path(__file__).parent / "mcp_cache.json"
LOG_FILE = Path(__file__).parent / "mcp_debug.log"

# Hosting configuration
PORT = int(os.getenv("PORT", 5001))
BASE_URL = os.getenv("BASE_URL", f"http://127.0.0.1:{PORT}").rstrip("/")
REDIRECT_URI = f"{BASE_URL}/mcp_callback"

def log_debug(message):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now().isoformat()} - {message}\n")

class NotAuthenticatedError(Exception):
    pass

def get_splitwise_client():
    """Return an authenticated Splitwise client using the dedicated MCP cache."""
    key = os.getenv("CONSUMER_KEY")
    secret = os.getenv("CONSUMER_SECRET")
    
    if not key or not secret:
        raise ValueError("Missing CONSUMER_KEY or CONSUMER_SECRET in .env file.")
        
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r") as f:
                cached = json.load(f)
                if "access_token" in cached:
                    return Splitwise(consumer_key=key, consumer_secret=secret, api_key=cached["access_token"])
    except Exception:
        pass

    raise NotAuthenticatedError()

# Initialize the FastMCP server
mcp = FastMCP("Splitwise-Analytics")

@mcp.app.route("/mcp_callback")
async def mcp_callback(request: Request):
    """Starlette route for Splitwise OAuth callback."""
    log_debug(f"Received callback request: {request.url}")
    
    code = request.query_params.get('code')
    if not code:
        log_debug("No code found in query parameters.")
        return PlainTextResponse("No code found in query parameters.", status_code=400)

    key = os.getenv("CONSUMER_KEY")
    secret = os.getenv("CONSUMER_SECRET")
    client = Splitwise(consumer_key=key, consumer_secret=secret)
    
    try:
        msg = f"Attempting token exchange with code: {code[:5]}... and redirect_uri: {REDIRECT_URI}"
        log_debug(msg)
        
        # Splitwise call is blocking, typically we'd wrap it in run_in_executor but for this purpose it's fine
        token_dict = client.getOAuth2AccessToken(code, REDIRECT_URI)
        log_debug(f"Token dict received: {token_dict.keys()}")
        
        access_token = token_dict.get("access_token")
        if access_token:
            with open(CACHE_FILE, "w") as f:
                json.dump({"access_token": access_token}, f)
            log_debug("Successfully saved access token to cache.")
            return HTMLResponse("<html><body><h2>Success!</h2><p>You have successfully logged in. You can close this tab and return to Claude.</p></body></html>")
        else:
            log_debug(f"No access token returned. Response: {token_dict}")
            return PlainTextResponse(f"No access token returned. Response: {token_dict}", status_code=500)
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        log_debug(f"Exception during token exchange: {str(e)}\n{error_detail}")
        return PlainTextResponse(f"Error during token exchange: {str(e)}\n\n{error_detail}", status_code=500)

auth_server_thread = None

@mcp.tool()
def login() -> str:
    """Generate a login link to authenticate this Claude session with your Splitwise account.
    Call this if any other Splitwise tool fails with an authentication error, or if the user asks to login.
    """
    global auth_server_thread
    key = os.getenv("CONSUMER_KEY")
    secret = os.getenv("CONSUMER_SECRET")
    
    if not key or not secret:
        return "Error: Splitwise API credentials missing from .env"
        
    client = Splitwise(consumer_key=key, consumer_secret=secret)
    url, state = client.getOAuth2AuthorizeURL(REDIRECT_URI)
    
    return f"Authentication required! Please click this link to authorize Splitwise:\n\n{url}\n\nOnce you see the 'Success' page, come back here and ask me to retry your request!"

@mcp.tool()
def get_current_user() -> str:
    """Get information about the currently authenticated Splitwise user."""
    try:
        client = get_splitwise_client()
        user = client.getCurrentUser()
        return f"User ID: {user.getId()}\nName: {user.getFirstName()} {user.getLastName() or ''}\nEmail: {user.getEmail()}\nDefault Currency: {user.getDefaultCurrency()}"
    except NotAuthenticatedError:
        return login()
    except Exception as e:
        return f"Error fetching current user: {str(e)}"

@mcp.tool()
def get_balance() -> str:
    """Get a high-level summary of your total balance (what you owe and what you are owed)."""
    try:
        client = get_splitwise_client()
        friends = client.getFriends()
        
        total_owed_to_me = defaultdict(float)
        total_i_owe = defaultdict(float)
        
        for friend in friends:
            for balance in friend.getBalances():
                amt = float(balance.getAmount())
                curr = balance.getCurrencyCode()
                if amt > 0:
                    total_owed_to_me[curr] += amt
                else:
                    total_i_owe[curr] += abs(amt)
        
        output = ["Overall Balances:"]
        currencies = set(list(total_owed_to_me.keys()) + list(total_i_owe.keys()))
        
        if not currencies:
            return "You are all settled up!"
            
        for curr in currencies:
            output.append(f"--- {curr} ---")
            output.append(f"You are owed: {round(total_owed_to_me[curr], 2)}")
            output.append(f"You owe: {round(total_i_owe[curr], 2)}")
            net = total_owed_to_me[curr] - total_i_owe[curr]
            output.append(f"Net Balance: {round(net, 2)}")
            
        return "\n".join(output)
    except NotAuthenticatedError:
        return login()
    except Exception as e:
        return f"Error fetching balance summary: {str(e)}"

@mcp.tool()
def get_groups() -> str:
    """Get a list of all your Splitwise groups, including their IDs and your current balance in each group.
    Use this to find the correct `group_id` before creating an expense.
    """
    try:
        client = get_splitwise_client()
        groups = client.getGroups()
        # Return a simplified string representation to save tokens
        lines = ["ID | Group Name | Balances"]
        for g in groups:
            if g.getId() != 0:
                # Create a simple balance string
                bals_str = "Settled up"
                bals = g.getBalances()
                if bals and len(bals) > 0:
                    # Filter out balances where the current user is not involved or amount is 0
                    user_balances = [b for b in bals if b.getAmount() != '0.0']
                    if user_balances:
                        bals_str = ", ".join([f"{b.getCurrencyCode()} {b.getAmount()}" for b in user_balances])
                    else:
                        bals_str = "Settled up"
                lines.append(f"{g.getId()} | {g.getName()} | {bals_str}")
        return "\n".join(lines)
    except NotAuthenticatedError:
        return login()
    except Exception as e:
        return f"Error fetching groups: {str(e)}"

@mcp.tool()
def get_friends() -> str:
    """Get a list of all your Splitwise friends, including their IDs and your current balance with them.
    Use this to find the correct `friend_id` if needed.
    """
    try:
        client = get_splitwise_client()
        friends = client.getFriends()
        lines = ["ID | Friend Name | Balances"]
        for f in friends:
            name = f"{f.getFirstName()} {f.getLastName() or ''}".strip()
            
            # Create a simple balance string
            bals_str = "Settled up"
            bals = f.getBalances()
            if bals and len(bals) > 0:
                bals_str = ", ".join([f"{b.getCurrencyCode()} {b.getAmount()}" for b in bals])
                
            lines.append(f"{f.getId()} | {name} | {bals_str}")
        return "\n".join(lines)
    except NotAuthenticatedError:
        return login()
    except Exception as e:
        return f"Error fetching friends: {str(e)}"

@mcp.tool()
def create_expense(group_id: int, amount: float, description: str) -> str:
    """Create a new expense in a specific Splitwise group. 
    Assumes the user paid the full amount and it is split equally among all group members.
    
    Args:
        group_id: The numerical ID of the Splitwise group (find this using get_groups tool first).
        amount: The total cost of the expense as a number (e.g. 24.50).
        description: A short description of what the expense is for (e.g. "Lunch at In-N-Out", "Gas").
    """
    try:
        client = get_splitwise_client()
        expense = Expense()
        expense.setGroupId(group_id)
        expense.setDescription(description)
        expense.setCost(str(amount))
        expense.setSplitEqually(True)
        
        # Make the API call
        created_expense, errors = client.createExpense(expense)
        
        if errors and errors.getErrors():
            return f"Failed to create expense. Splitwise API Error: {errors.getErrors()}"
            
        return f"Successfully created expense '{description}' for {amount} in group {group_id}."
    except NotAuthenticatedError:
        return login()
    except Exception as e:
        return f"An exception occurred while creating the expense: {str(e)}"

@mcp.tool()
def get_expenses(months: int = 12, group_id: int = None) -> str:
    """Fetch a list of expenses for the last N months.
    Useful for analyzing spending patterns and totals over time.
    
    Args:
        months: Number of months of history to fetch (default 12).
        group_id: Optional numerical ID of a specific group to filter by.
    """
    try:
        client = get_splitwise_client()
        current_user = client.getCurrentUser()
        my_id = current_user.getId()
        
        start_date = date.today() - relativedelta(months=months)
        
        kwargs = {
            "dated_after": start_date.isoformat(),
            "limit": 0, # 0 usually means all, but let's be careful. Splitwise limit is often 50-100.
            "visible": True
        }
        if group_id:
            kwargs["group_id"] = group_id
            
        expenses = client.getExpenses(**kwargs)
        
        if not expenses:
            return f"No expenses found for the last {months} months."
            
        lines = ["Date | Description | Category | Total Cost | My Share | Currency"]
        for e in expenses:
            # Skip payments
            if e.getPayment():
                continue
            if e.getCreationMethod() == "debt_consolidation":
                continue
                
            cat = e.getCategory().getName() if e.getCategory() else "Uncategorized"
            total = e.getCost()
            currency = e.getCurrencyCode()
            
            # Find my share
            my_share = 0.0
            for u in e.getUsers():
                if u.getId() == my_id:
                    my_share = float(u.getOwedShare())
                    break
            
            lines.append(f"{e.getDate()[:10]} | {e.getDescription()} | {cat} | {total} | {my_share} | {currency}")
            
        return "\n".join(lines)
    except NotAuthenticatedError:
        return login()
    except Exception as e:
        return f"Error fetching expenses: {str(e)}"

@mcp.tool()
def get_spending_summary(months: int = 12) -> str:
    """Get a summary of spending aggregated by category for the last N months.
    This is best for answering "Where am I spending the most money?".
    """
    try:
        client = get_splitwise_client()
        current_user = client.getCurrentUser()
        my_id = current_user.getId()
        
        start_date = date.today() - relativedelta(months=months)
        expenses = client.getExpenses(dated_after=start_date.isoformat(), limit=0, visible=True)
        
        category_totals = defaultdict(lambda: defaultdict(float))
        
        for e in expenses:
            if e.getPayment() or e.getCreationMethod() == "debt_consolidation":
                continue
                
            currency = e.getCurrencyCode()
            cat = e.getCategory().getName() if e.getCategory() else "Uncategorized"
            
            my_share = 0.0
            for u in e.getUsers():
                if u.getId() == my_id:
                    my_share = float(u.getOwedShare())
                    break
            
            category_totals[currency][cat] += my_share
            
        if not category_totals:
            return "No spending data found for the selected period."
            
        lines = ["Currency | Category | Total Spent (My Share)"]
        for curr, cats in category_totals.items():
            # Sort categories by spending amount descending
            sorted_cats = sorted(cats.items(), key=lambda x: x[1], reverse=True)
            for cat, total in sorted_cats:
                lines.append(f"{curr} | {cat} | {round(total, 2)}")
                
        return "\n".join(lines)
    except NotAuthenticatedError:
        return login()
    except Exception as e:
        return f"Error generating spending summary: {str(e)}"

@mcp.tool()
def get_monthly_trends(months: int = 12) -> str:
    """Get a summary of total spending per month for the last N months.
    Useful for answering "How has my spending changed over the last year?".
    """
    try:
        client = get_splitwise_client()
        current_user = client.getCurrentUser()
        my_id = current_user.getId()
        
        start_date = date.today() - relativedelta(months=months)
        expenses = client.getExpenses(dated_after=start_date.isoformat(), limit=0, visible=True)
        
        monthly_totals = defaultdict(lambda: defaultdict(float))
        
        for e in expenses:
            if e.getPayment() or e.getCreationMethod() == "debt_consolidation":
                continue
                
            currency = e.getCurrencyCode()
            month = e.getDate()[:7] # YYYY-MM
            
            my_share = 0.0
            for u in e.getUsers():
                if u.getId() == my_id:
                    my_share = float(u.getOwedShare())
                    break
            
            monthly_totals[currency][month] += my_share
            
        if not monthly_totals:
            return "No spending data found for the selected period."
            
        lines = ["Currency | Month | Total Spent (My Share)"]
        for curr, months_data in monthly_totals.items():
            # Sort by month string
            sorted_months = sorted(months_data.items(), key=lambda x: x[0])
            for m, total in sorted_months:
                lines.append(f"{curr} | {m} | {round(total, 2)}")
                
        return "\n".join(lines)
    except NotAuthenticatedError:
        return login()
    except Exception as e:
        return f"Error generating monthly trends: {str(e)}"

if __name__ == "__main__":
    # In production/docker, we'll usually run with transport="sse"
    # To run locally with stdio (default), just run: python mcp_server.py
    # To run as SSE: python mcp_server.py sse
    import sys
    host = "0.0.0.0" if os.getenv("DOCKER") else "127.0.0.1"
    
    if len(sys.argv) > 1 and sys.argv[1] == "sse":
        print(f"Starting Splitwise MCP Server on SSE port {PORT}...")
        mcp.run(transport="sse", host=host, port=PORT)
    else:
        mcp.run()
