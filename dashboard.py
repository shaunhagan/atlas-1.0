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

Structure is a risk-tiered menu: each trading approach is its own
independently tracked "book" -- Safe (crypto + stocks, the validated,
disciplined tier), Medium (AI/news-driven, placeholder pending an LLM
API key decision), and High (meme coins, deliberately aggressive by
design). Never blended together, so a reader can judge each on its own
merits, matching how the underlying systems are actually kept separate.
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
)
from dotenv import load_dotenv

import portfolio
import report

import stock_portfolio
import stock_report

import meme_portfolio
import meme_report


load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("DASHBOARD_SECRET_KEY") or os.urandom(24).hex()

DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD")

EQUITY_CURVE_POINT_LIMIT = 500

RECENT_TRADES_LIMIT = 20


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
# DATA LAYER -- reuses report.py / stock_report.py directly
# ============================================================

def _book_summary(portfolio_module, report_module):
    """
    Same numbers report.py/stock_report.py print on the CLI, reused
    directly rather than re-derived, so the dashboard can never
    silently disagree with `python report.py`.
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


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
@login_required
def home():

    crypto = _book_summary(portfolio, report)
    stocks = _book_summary(stock_portfolio, stock_report)
    meme = _book_summary(meme_portfolio, meme_report)

    return render_template(
        "dashboard.html",
        crypto=crypto,
        stocks=stocks,
        meme=meme,
    )


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

    app.run(host="127.0.0.1", port=5000, debug=False)
