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

Sidebar-navigated multi-page layout: a combined "Dashboard" home page
(cross-book totals, system status, market movers), per-book deep-dive
pages, and dedicated Trade History / Open Positions / Performance /
Analytics / Watchlist / Settings pages. Every number here is real,
derived from actual logs/config or a live exchange call -- nothing
fabricated (see dashboard_data.get_market_signal()'s docstring for
why the "AI sentiment"-shaped widget is a real technical read, not AI).
"""

import json
import os
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    abort,
    flash,
)
from dotenv import load_dotenv

import config
import portfolio
import report
import exchange as crypto_exchange

import stock_portfolio
import stock_report
import stock_scanner
import stock_exchange as stock_exchange_module

import meme_portfolio
import meme_report
import meme_exchange as meme_exchange_module

import report_utils
import dashboard_data
import wallet


load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("DASHBOARD_SECRET_KEY") or os.urandom(24).hex()

DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD")

RECENT_TRADES_LIMIT = 20

WATCHLIST_FILE = Path("data") / "watchlist.json"

FOOTER_QUOTES = [
    "Discipline compounds tomorrow.",
    "Validate, then trust.",
    "The backtest is the argument.",
    "No excuses, no shortcuts.",
]


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
        "exchange_instance": crypto_exchange.exchange,
        "scan_interval": config.SCAN_INTERVAL,
        "is_market_open_fn": None,
        "signal_type": "trend",
        "min_confidence": config.MIN_CONFIDENCE,
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
        "exchange_instance": stock_exchange_module.exchange,
        "scan_interval": config.STOCK_SCAN_INTERVAL,
        "is_market_open_fn": lambda: stock_scanner.is_market_open()[0],
        "signal_type": "mean_reversion",
        "min_confidence": None,
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
        "exchange_instance": meme_exchange_module.exchange,
        "scan_interval": config.MEME_SCAN_INTERVAL,
        "is_market_open_fn": None,
        "signal_type": "trend",
        "min_confidence": config.MEME_MIN_CONFIDENCE,
    },
}

BOOK_DEFS_TRADES = [(k, m["label"], m["report_module"]) for k, m in BOOKS.items()]
BOOK_DEFS_POSITIONS = [(k, m["label"], m["portfolio_module"]) for k, m in BOOKS.items()]


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
# SHARED TEMPLATE CONTEXT -- every page that extends base.html
# gets these automatically, so routes don't repeat them.
# ============================================================

@app.context_processor
def inject_shell_context():

    try:
        notifications = dashboard_data.get_notifications(BOOK_DEFS_TRADES, lookback_hours=24, limit=8)
    except Exception:
        notifications = []

    import random

    return {
        "dashboard_username": DASHBOARD_USERNAME,
        "notification_count": len(notifications),
        "notification_summary": (
            f"{len(notifications)} events in the last 24h" if notifications else "No new alerts"
        ),
        "footer_quote": random.choice(FOOTER_QUOTES),
    }


# ============================================================
# DATA LAYER -- reuses report.py / stock_report.py / report_utils.py
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

        full_equity_curve = [
            {
                "label": f"{row['Date']} {row['Time']}",
                "equity": float(row["TotalEquity"]),
            }
            for row in equity_rows
        ]

        # Telescoping downsample (full resolution recently, compressed
        # further back) rather than a flat tail-truncate -- a flat
        # cap at EQUITY_CURVE_POINT_LIMIT raw rows meant "1M"/"3M"/
        # "ALL" range views on the book detail page couldn't actually
        # show that much history once a book's equity log grew past a
        # few thousand rows (logged every ~30s).
        equity_curve = report_utils.downsample_curve(full_equity_curve)

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
# ROUTES -- main dashboard
# ============================================================

@app.route("/")
@login_required
def home():

    per_book = {}

    for key, meta in BOOKS.items():
        per_book[key] = _book_summary(meta["portfolio_module"], meta["report_module"])

    ok_books = [b for b in per_book.values() if b["ok"]]

    total_equity = sum(b["total_equity"] for b in ok_books)
    total_starting = sum(b["starting_balance"] for b in ok_books)
    total_return_pct = (total_equity / total_starting - 1) * 100 if total_starting else 0.0

    total_realised = sum(b["realised_pnl"] for b in ok_books)
    total_unrealised = total_equity - total_starting - total_realised if total_starting else 0.0

    total_wins = sum(b["wins"] for b in ok_books)
    total_losses = sum(b["losses"] for b in ok_books)
    total_closed = total_wins + total_losses
    overall_win_rate = (total_wins / total_closed * 100) if total_closed else 0.0

    total_open_positions = sum(len(b["open_positions"]) for b in per_book.values() if b["ok"])

    # Wallet-style summary: cash actually free to trade with vs cash
    # tied up in open positions, mirroring how a real brokerage
    # account splits "buying power" from "invested". position_value
    # isn't returned by _book_summary directly, but equity = cash +
    # position_value, so it's derivable without re-reading the files.
    total_available_cash = sum(b["balance"] for b in ok_books)
    total_in_positions = sum(b["total_equity"] - b["balance"] for b in ok_books)

    todays_pnl = 0.0
    for key, meta in BOOKS.items():
        equity_rows = meta["report_module"].load_equity_curve()
        daily = report_utils.group_by_period(equity_rows, "day")
        if daily:
            todays_pnl += daily[-1]["pnl"]

    all_pnls = []
    for key, meta in BOOKS.items():
        trades = meta["report_module"].load_trades()
        closed, _, _ = meta["report_module"].summarise_trades(trades)
        all_pnls.extend(t["pnl"] for t in closed)

    avg_trade_size = (sum(abs(p) for p in all_pnls) / len(all_pnls)) if all_pnls else 0.0

    full_combined_curve = dashboard_data.combined_equity_curve(
        [(k, m["label"], m["report_module"]) for k, m in BOOKS.items()],
    )

    total_max_drawdown = report_utils.max_drawdown_from_curve(full_combined_curve)

    # Full history for accuracy server-side, but only a downsampled
    # version is sent to the browser -- an all-points equity log can
    # run into the tens of thousands of rows, which bloats the page
    # for no visible benefit on a line chart.
    combined_curve = report_utils.downsample_curve(full_combined_curve)

    performance_periods = {}
    for period in ("day", "week", "month", "year"):
        rows = {}
        for key, meta in BOOKS.items():
            equity_rows = meta["report_module"].load_equity_curve()
            grouped = report_utils.group_by_period(
                equity_rows, "day" if period == "week" else period,
            )
            rows[key] = grouped[-1]["pnl_pct"] if grouped else 0.0
        rows["overall"] = sum(rows.values()) / len(rows) if rows else 0.0
        performance_periods[period] = rows

    status_by_book = {}
    for key, meta in BOOKS.items():
        status_by_book[key] = dashboard_data.get_system_status(
            meta["report_module"].TRADE_LOG,
            meta["scan_interval"],
            meta["is_market_open_fn"],
        )

    any_running = any(s["running"] for s in status_by_book.values())

    connectivity_by_book = {
        key: dashboard_data.check_exchange_connectivity(meta["exchange_instance"])
        for key, meta in BOOKS.items()
    }

    movers = dashboard_data.get_top_movers(crypto_exchange.exchange)

    market_signal = dashboard_data.get_market_signal(crypto_exchange.exchange)

    recent_trades = dashboard_data.combined_trades(BOOK_DEFS_TRADES, limit=RECENT_TRADES_LIMIT)
    open_positions = dashboard_data.combined_open_positions(BOOK_DEFS_POSITIONS)
    notifications = dashboard_data.get_notifications(BOOK_DEFS_TRADES, limit=8)

    return render_template(
        "home.html",
        active_nav="dashboard",
        per_book=per_book,
        books_meta=BOOKS,
        total_equity=total_equity,
        total_starting=total_starting,
        total_return_pct=total_return_pct,
        total_realised=total_realised,
        total_unrealised=total_unrealised,
        overall_win_rate=overall_win_rate,
        total_wins=total_wins,
        total_losses=total_losses,
        total_closed=total_closed,
        total_open_positions=total_open_positions,
        total_available_cash=total_available_cash,
        total_in_positions=total_in_positions,
        total_max_drawdown=total_max_drawdown,
        todays_pnl=todays_pnl,
        avg_trade_size=avg_trade_size,
        combined_curve=combined_curve,
        performance_periods=performance_periods,
        status_by_book=status_by_book,
        connectivity_by_book=connectivity_by_book,
        any_running=any_running,
        movers=movers,
        market_signal=market_signal,
        recent_trades=recent_trades,
        open_positions=open_positions,
        notifications=notifications,
        format_uptime=dashboard_data.format_uptime,
        format_ago=dashboard_data.format_ago,
    )


def _signal_reasoning_for(meta, symbol):

    if meta["signal_type"] == "mean_reversion":
        return dashboard_data.mean_reversion_reasoning(meta["exchange_instance"], symbol)

    return dashboard_data.trend_engine_reasoning(
        meta["exchange_instance"], symbol, meta["min_confidence"],
    )


@app.route("/book/<key>")
@login_required
def book_detail(key):

    meta = BOOKS.get(key)

    if meta is None:
        abort(404)

    detail = _book_detail(meta["portfolio_module"], meta["report_module"])

    health = dashboard_data.compute_strategy_health(meta["report_module"])

    connected = dashboard_data.check_exchange_connectivity(meta["exchange_instance"])

    explanations = []

    if detail.get("ok"):

        # Live-recomputed signal reasoning for open positions only (a
        # handful of symbols at most) -- not run against the whole
        # scan universe, to keep this page fast to load.
        for position in detail["open_positions"][:6]:

            reasoning = _signal_reasoning_for(meta, position["symbol"])

            if reasoning:
                explanations.append(reasoning)

    return render_template(
        "book_detail.html",
        active_nav=key,
        key=key,
        label=meta["label"],
        color=meta["color"],
        tier=meta["tier"],
        tagline=meta["tagline"],
        description=meta["description"],
        book=detail,
        health=health,
        connected=connected,
        explanations=explanations,
    )


@app.route("/trade-history")
@login_required
def trade_history():

    book_filter = request.args.get("book")

    trades = dashboard_data.combined_trades(BOOK_DEFS_TRADES)

    if book_filter:
        trades = [t for t in trades if t["book_key"] == book_filter]

    return render_template(
        "trade_history.html",
        active_nav="trade_history",
        trades=trades,
        books_meta=BOOKS,
        book_filter=book_filter,
    )


@app.route("/open-positions")
@login_required
def open_positions():

    positions = dashboard_data.combined_open_positions(BOOK_DEFS_POSITIONS)

    return render_template(
        "open_positions.html",
        active_nav="open_positions",
        positions=positions,
        books_meta=BOOKS,
    )


@app.route("/performance")
@login_required
def performance():

    per_book_periods = {}

    for key, meta in BOOKS.items():

        equity_rows = meta["report_module"].load_equity_curve()

        per_book_periods[key] = {
            "daily": list(reversed(report_utils.group_by_period(equity_rows, "day")))[:30],
            "monthly": list(reversed(report_utils.group_by_period(equity_rows, "month"))),
            "annual": list(reversed(report_utils.group_by_period(equity_rows, "year"))),
        }

    return render_template(
        "performance.html",
        active_nav="performance",
        books_meta=BOOKS,
        per_book_periods=per_book_periods,
    )


@app.route("/analytics")
@login_required
def analytics():

    per_book_analytics = {}

    for key, meta in BOOKS.items():

        trades = meta["report_module"].load_trades()
        closed, wins, losses = meta["report_module"].summarise_trades(trades)

        reason_counts = {}
        for trade in closed:
            reason_counts[trade["reason"]] = reason_counts.get(trade["reason"], 0) + 1

        ranked = sorted(closed, key=lambda t: t["pnl"], reverse=True)

        per_book_analytics[key] = {
            "closed_count": len(closed),
            "win_rate": (len(wins) / len(closed) * 100) if closed else 0.0,
            "reason_counts": reason_counts,
            "top_winners": ranked[:5],
            "top_losers": ranked[-5:][::-1] if closed else [],
        }

    return render_template(
        "analytics.html",
        active_nav="analytics",
        books_meta=BOOKS,
        per_book_analytics=per_book_analytics,
    )


@app.route("/settings")
@login_required
def settings():

    settings_by_book = {
        "crypto": {
            "Exchange": config.EXCHANGE, "Timeframe": config.TIMEFRAME,
            "Scan Limit": config.SCAN_LIMIT, "Scan Interval (s)": config.SCAN_INTERVAL,
            "Risk / Trade": f"{config.RISK_PER_TRADE * 100:.1f}%",
            "ATR Stop Multiplier": config.ATR_STOP_MULTIPLIER,
            "Risk:Reward": config.RISK_REWARD_RATIO,
            "Max Open Trades": config.MAX_OPEN_TRADES,
            "Daily Loss Limit": f"{config.DAILY_LOSS_LIMIT_PCT:.1f}%",
            "Min Confidence": config.MIN_CONFIDENCE,
        },
        "stocks": {
            "Timeframe (min)": config.STOCK_TIMEFRAME_MINUTES, "Scan Limit": config.STOCK_SCAN_LIMIT,
            "Scan Interval (s)": config.STOCK_SCAN_INTERVAL,
            "Risk / Trade": f"{config.STOCK_RISK_PER_TRADE * 100:.1f}%",
            "ATR Stop Multiplier": config.STOCK_ATR_STOP_MULTIPLIER,
            "Risk:Reward": config.STOCK_RISK_REWARD_RATIO,
            "Max Open Trades": config.STOCK_MAX_OPEN_TRADES,
            "Strategy": "Bollinger Band + RSI mean reversion",
            "Bollinger Period / StdDev": f"{config.BOLLINGER_PERIOD} / {config.BOLLINGER_STDDEV}",
            "RSI Oversold": config.MEANREV_RSI_OVERSOLD,
        },
        "meme": {
            "Scan Limit": config.MEME_SCAN_LIMIT, "Scan Interval (s)": config.MEME_SCAN_INTERVAL,
            "Risk / Trade": f"{config.MEME_RISK_PER_TRADE * 100:.1f}%",
            "ATR Stop Multiplier": config.MEME_ATR_STOP_MULTIPLIER,
            "Min Stop Distance": f"{config.MEME_MIN_STOP_DISTANCE_PCT:.2f}%",
            "Risk:Reward": config.MEME_RISK_REWARD_RATIO,
            "Max Open Trades": config.MEME_MAX_OPEN_TRADES,
            "Daily Loss Limit": f"{config.MEME_DAILY_LOSS_LIMIT_PCT:.1f}%",
            "Min Confidence": config.MEME_MIN_CONFIDENCE,
        },
    }

    return render_template(
        "settings.html",
        active_nav="settings",
        settings_by_book=settings_by_book,
        books_meta=BOOKS,
    )


@app.route("/news")
@login_required
def news_placeholder():

    return render_template("news_placeholder.html", active_nav="news")


# ============================================================
# WALLET -- real simulated-capital ledger. See wallet.py's docstring
# for why deposits/withdrawals are real balance changes (via each
# book's existing update_balance()) rather than decorative, and why
# this is unambiguously paper money, never live funds.
# ============================================================

RISK_LIMITS_BY_BOOK = {
    "crypto": {
        "Risk per Trade": f"{config.RISK_PER_TRADE * 100:.1f}%",
        "Max Open Trades": config.MAX_OPEN_TRADES,
        "Daily Loss Limit": f"{config.DAILY_LOSS_LIMIT_PCT:.1f}%",
    },
    "stocks": {
        "Risk per Trade": f"{config.STOCK_RISK_PER_TRADE * 100:.1f}%",
        "Max Open Trades": config.STOCK_MAX_OPEN_TRADES,
        "Daily Loss Limit": f"{config.DAILY_LOSS_LIMIT_PCT:.1f}%",
    },
    "meme": {
        "Risk per Trade": f"{config.MEME_RISK_PER_TRADE * 100:.1f}%",
        "Max Open Trades": config.MEME_MAX_OPEN_TRADES,
        "Daily Loss Limit": f"{config.MEME_DAILY_LOSS_LIMIT_PCT:.1f}%",
    },
}


@app.route("/wallet")
@login_required
def wallet_page():

    per_book_wallet = {}

    for key, meta in BOOKS.items():

        summary = _book_summary(meta["portfolio_module"], meta["report_module"])

        if not summary["ok"]:
            continue

        per_book_wallet[key] = {
            "label": meta["label"],
            "color": meta["color"],
            "cash": summary["balance"],
            "in_positions": summary["total_equity"] - summary["balance"],
            "equity": summary["total_equity"],
            "unrealised": summary["total_equity"] - summary["starting_balance"] - summary["realised_pnl"],
            "realised": summary["realised_pnl"],
            "risk_limits": RISK_LIMITS_BY_BOOK.get(key, {}),
        }

    total_portfolio = sum(b["equity"] for b in per_book_wallet.values())
    total_cash = sum(b["cash"] for b in per_book_wallet.values())
    total_in_positions = sum(b["in_positions"] for b in per_book_wallet.values())
    total_unrealised = sum(b["unrealised"] for b in per_book_wallet.values())
    total_realised = sum(b["realised"] for b in per_book_wallet.values())

    transactions = wallet.load_transactions(limit=100)

    total_deposits = sum(t["amount"] for t in transactions if t["type"] == "deposit" and t["status"] == "completed")
    total_withdrawals = sum(t["amount"] for t in transactions if t["type"] == "withdrawal" and t["status"] == "completed")

    return render_template(
        "wallet.html",
        active_nav="wallet",
        books_meta=BOOKS,
        per_book_wallet=per_book_wallet,
        total_portfolio=total_portfolio,
        total_cash=total_cash,
        total_in_positions=total_in_positions,
        total_unrealised=total_unrealised,
        total_realised=total_realised,
        total_deposits=total_deposits,
        total_withdrawals=total_withdrawals,
        transactions=transactions,
    )


@app.route("/wallet/deposit", methods=["POST"])
@login_required
def wallet_deposit():

    key = request.form.get("book")
    meta = BOOKS.get(key)

    try:
        amount = float(request.form.get("amount", 0))
    except ValueError:
        amount = 0

    if meta is None:
        flash("Unknown book.", "error")
        return redirect(url_for("wallet_page"))

    ok, message = wallet.deposit(meta["portfolio_module"], key, meta["label"], amount)

    flash(message, "success" if ok else "error")

    return redirect(url_for("wallet_page"))


@app.route("/wallet/withdraw", methods=["POST"])
@login_required
def wallet_withdraw():

    key = request.form.get("book")
    meta = BOOKS.get(key)

    try:
        amount = float(request.form.get("amount", 0))
    except ValueError:
        amount = 0

    if meta is None:
        flash("Unknown book.", "error")
        return redirect(url_for("wallet_page"))

    ok, message = wallet.withdraw(meta["portfolio_module"], key, meta["label"], amount)

    flash(message, "success" if ok else "error")

    return redirect(url_for("wallet_page"))


# ============================================================
# WATCHLIST -- a small real feature: persisted symbol list + live
# prices, stored locally since this project has no database.
# ============================================================

def _load_watchlist():

    if not WATCHLIST_FILE.exists():
        return []

    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as file:
            return json.load(file).get("symbols", [])
    except Exception:
        return []


def _save_watchlist(symbols):

    WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(WATCHLIST_FILE, "w", encoding="utf-8") as file:
        json.dump({"symbols": symbols}, file, indent=2)


@app.route("/watchlist", methods=["GET", "POST"])
@login_required
def watchlist():

    if request.method == "POST":

        symbol = request.form.get("symbol", "").strip().upper()

        if symbol:

            symbols = _load_watchlist()

            if symbol not in symbols:
                symbols.append(symbol)
                _save_watchlist(symbols)

        return redirect(url_for("watchlist"))

    symbols = _load_watchlist()

    rows = []

    try:
        tickers = crypto_exchange.exchange.exchange.fetch_tickers()
    except Exception:
        tickers = {}

    for symbol in symbols:

        data = tickers.get(symbol)

        rows.append({
            "symbol": symbol,
            "price": data.get("last") if data else None,
            "change_pct": data.get("percentage") if data else None,
            "found": data is not None,
        })

    return render_template("watchlist.html", active_nav="watchlist", rows=rows)


@app.route("/watchlist/remove/<path:symbol>", methods=["POST"])
@login_required
def watchlist_remove(symbol):

    symbols = [s for s in _load_watchlist() if s != symbol]

    _save_watchlist(symbols)

    return redirect(url_for("watchlist"))


# ============================================================
# JSON APIs (kept for external/API use)
# ============================================================

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
