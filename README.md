# Splitwise Analytics

A premium analytics dashboard for your Splitwise expenses. Connect via OAuth 2.0 and unlock powerful insights into your spending patterns, category breakdowns, group finances, and more.

## Features

- **Dashboard** — At-a-glance summary: balances, groups count, friends count, plus mini charts
- **Monthly Spending** — Stacked bar chart of expenses by category, with date-range selector and data table
- **Category Breakdown** — Doughnut chart showing where your money goes, with percentage table
- **Groups** — All your Splitwise groups with balance summaries; click through for group-level expense details
- **Friends** — Friend list with multi-currency balance indicators
- **Spending Trends** — Line chart of month-over-month total spending with average/min/max stats
- **Secure OAuth 2.0** — No passwords stored; uses Splitwise's official OAuth flow

## Tech Stack

- **Backend:** Python / Flask
- **Frontend:** Jinja2 templates, Chart.js, vanilla CSS (dark glassmorphism design)
- **API:** Splitwise Python SDK (`splitwise`)
- **Deployment:** Docker + Nginx reverse proxy

## Getting Started

### 1. Set Up OAuth Credentials

1. Go to the [Splitwise Developer Portal](https://www.splitwise.com/apps)
2. Create a new application
3. Note your **Consumer Key** and **Consumer Secret**

### 2. Configure Environment

Create a `.env` file in the project root:

```
CONSUMER_KEY = "your_key_here"
CONSUMER_SECRET = "your_secret_here"
```

### 3. Run Locally

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 in your browser.

### 4. Run with Docker

```bash
docker compose up -d
```

Open http://localhost in your browser.

## FAQ

**What if I have expenses in multiple currencies?**
Only your default currency expenses are used for charts and analytics. Set your preferred currency as the default in the Splitwise app.

## Acknowledgements

- [Splitwise API](https://dev.splitwise.com/)
- [Chart.js](https://www.chartjs.org/)