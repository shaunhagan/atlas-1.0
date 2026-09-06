"""
=========================================
ATLAS AI
Web Dashboard
=========================================

Local-only Flask app (login-protected, per the original day-one goal
of "log in and see what's going on"). Reads directly from the same
files report.py/stock_report.py already read -- no separate data
layer, no risk of showing something different from what those CLI
reports say.

Structure: a landing page with one card per book (Crypto, Stocks,
Meme Coins, and a not-yet-live AI/News section), each linking to its
own deep-dive page with the full trade history and daily/monthly/
annual breakdowns -- not a single page trying to show everything at
once. Books stay independently rendered, matching how the underlying
systems are actually kept separate.
"""

import os
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    abort,
)
from dotenv import load_dotenv

import portfolio
import report

import stock_portfolio
import stock_report

import meme_portfolio
import meme_report

import report_utils


load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("DASHBOARD_SECRET_KEY") or os.urandom(24).hex()

DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD")

EQUITY_CURVE_POINT_LIMIT = 500

RECENT_TRADES_LIMIT = 20


BOOKS = {
    "crypto": {
        "label": "Crypto",
        "color": "#4fd1c5",
        "tier": "Safe",
        "tagline": "Trend-following, 24/7",
        "description": (
            "EMA/RSI/MACD trend engine across ~60 liquid Binance USDT "
            "pairs. Validated through a full backtest -> train/test -> "
            "parameter sweep -> ablation sequence. The longest-running, "
            "most disciplined book."
        ),
        "portfolio_module": portfolio,
        "report_module": report,
    },
    "stocks": {
        "label": "Stocks",
        "color": "#818cf8",
        "tier": "Safe",
        "tagline": "Mean reversion, US market hours",
        "description": (
            "Bollinger Band + RSI mean reversion across ~50 liquid, "
            "volume-ranked US equities (leveraged/inverse ETFs excluded). "
            "Replaced a trend-following engine that proved dead both in "
            "backtest and live."
        ),
        "portfolio_module": stock_portfolio,
        "report_module": stock_report,
    },
    "meme": {
        "label": "Meme Coins",
        "color": "#fb923c",
        "tier": "High Risk",
        "tagline": "Aggressive, no regime gate",
        "description": (
            "Same trend engine as crypto, tuned looser and wider, across "
            "~22 meme coins on Kraken. Deliberately the riskiest book -- "
            "wide stops, low win rate by design, big infrequent winners."
        ),
        "portfolio_module": meme_portfolio,
        "report_module": meme_report,
    },
}


# ============================================================
# AUTH
# ============================================================

def login_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not session.get("logged_in"):
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():

    error = None

    if request.method == "POST":

        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if (
            DASHBOARD_USERNAME
            and DASHBOARD_PASSWORD
            and username == DASHBOARD_USERNAME
            and password == DASHBOARD_PASSWORD
        ):

            session["logged_in"] = True

            return redirect(url_for("home"))

        error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ============================================================
# DATA LAYER -- reuses report.py / stock_report.py / report_utils.py
# ============================================================

def _book_summary(portfolio_module, report_module):
    """
    Same numbers report.py/stock_report.py print on the CLI, reused
    directly rather than re-derived, so the dashboard can never
    silently disagree with `python report.py`. Used for the landing
    page cards (a quick-glance stat) and as the base for the detail
    page.
    """

    try:

        summary = portfolio_module.get_summary()

        trades = report_module.load_trades()
        equity_rows = report_module.load_equity_curve()

        closed, wins, losses = report_module.summarise_trades(trades)

        if equity_rows:
            first_equity = float(equity_rows[0]["TotalEquity"])
            last_equity = float(equity_rows[-1]["TotalEquity"])
        else:
            first_equity = summary["starting_balance"]
            last_equity = summary["starting_balance"]

        total_return_pct = (
            (last_equity / first_equity - 1) * 100
            if first_equity else 0.0
        )

        win_rate = (
            len(wins) / len(closed) * 100
            if closed else 0.0
        )

        avg_win = (
            sum(trade["pnl"] for trade in wins) / len(wins)
            if wins else 0.0
        )

        avg_loss = (
            sum(trade["pnl"] for trade in losses) / len(losses)
            if losses else 0.0
        )

        equity_curve = [
            {
                "label": f"{row['Date']} {row['Time']}",
                "equity": float(row["TotalEquity"]),
            }
            for row in equity_rows[-EQUITY_CURVE_POINT_LIMIT:]
        ]

        recent_trades = list(reversed(trades[-RECENT_TRADES_LIMIT:]))

        open_positions = [
            {
                "symbol": symbol,
                "entry_price": float(position.get("entry_price", 0.0)),
                "quantity": float(position.get("quantity", 0.0)),
                "stop_loss": position.get("stop_loss"),
                "take_profit": position.get("take_profit"),
                "position_value": float(position.get("position_value", 0.0)),
            }
            for symbol, position in summary["positions"].items()
        ]

        return {
            "ok": True,
            "balance": summary["balance"],
            "starting_balance": summary["starting_balance"],
            "total_equity": last_equity,
            "total_return_pct": total_return_pct,
            "max_drawdown": report_module.max_drawdown(equity_rows),
            "realised_pnl": summary["realised_pnl"],
            "closed_trades": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "open_positions": open_positions,
            "equity_curve": equity_curve,
            "recent_trades": recent_trades,
        }

    except Exception as error:

        return {"ok": False, "error": str(error)}


def _book_detail(portfolio_module, report_module):
    """Everything _book_summary has, plus the full trade history and
    daily/monthly/annual breakdowns for the deep-dive page."""

    summary = _book_summary(portfolio_module, report_module)

    if not summary["ok"]:
        return summary

    try:

        trades = report_module.load_trades()
        equity_rows = report_module.load_equity_curve()

        summary["full_trades"] = report_utils.full_trade_history(trades)
        summary["daily"] = list(reversed(report_utils.group_by_period(equity_rows, "day")))
        summary["monthly"] = list(reversed(report_utils.group_by_period(equity_rows, "month")))
        summary["annual"] = list(reversed(report_utils.group_by_period(equity_rows, "year")))

        return summary

    except Exception as error:

        return {"ok": False, "error": str(error)}


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
@login_required
def home():

    cards = []

    for key, meta in BOOKS.items():

        summary = _book_summary(meta["portfolio_module"], meta["report_module"])

        cards.append({
            "key": key,
            "label": meta["label"],
            "color": meta["color"],
            "tier": meta["tier"],
            "tagline": meta["tagline"],
            "description": meta["description"],
            "summary": summary,
        })

    return render_template("home.html", cards=cards)


@app.route("/book/<key>")
@login_required
def book_detail(key):

    meta = BOOKS.get(key)

    if meta is None:
        abort(404)

    detail = _book_detail(meta["portfolio_module"], meta["report_module"])

    return render_template(
        "book_detail.html",
        key=key,
        label=meta["label"],
        color=meta["color"],
        tier=meta["tier"],
        tagline=meta["tagline"],
        description=meta["description"],
        book=detail,
    )


@app.route("/news")
@login_required
def news_placeholder():

    return render_template("news_placeholder.html")


@app.route("/api/crypto")
@login_required
def api_crypto():

    return jsonify(_book_summary(portfolio, report))


@app.route("/api/stocks")
@login_required
def api_stocks():

    return jsonify(_book_summary(stock_portfolio, stock_report))


@app.route("/api/meme")
@login_required
def api_meme():

    return jsonify(_book_summary(meme_portfolio, meme_report))


if __name__ == "__main__":

    if not DASHBOARD_USERNAME or not DASHBOARD_PASSWORD:

        print(
            "WARNING: DASHBOARD_USERNAME/DASHBOARD_PASSWORD not set "
            "in .env -- login will always fail until they are."
        )

    # 0.0.0.0 so it's reachable from other devices on the Tailscale
    # network (and the local LAN) -- still login-gated either way,
    # not exposed to the wider internet since nothing forwards this
    # port publicly.
    app.run(host="0.0.0.0", port=5000, debug=False)
