"""
=========================================
ATLAS AI
Dashboard Aggregation Layer
=========================================

Cross-book helpers for the dashboard's combined "Dashboard" home page
and its System Status / Top Movers / Notifications widgets. Everything
here is read-only and derived from real data already on disk or from
a real exchange call -- nothing here is fabricated. Where the picture
this was modelled on showed something Atlas doesn't actually have yet
(a true AI-sentiment engine), the equivalent widget here is built from
real technical data and labelled honestly, not faked.
"""

import csv
from datetime import datetime, timedelta

import report_utils


# ============================================================
# SYSTEM STATUS -- derived entirely from existing log files, no
# new heartbeat file or change to the live bots needed.
# ============================================================

def _load_raw_rows(csv_path):

    if not csv_path.exists():
        return []

    with open(csv_path, "r", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def get_system_status(csv_path, scan_interval_seconds, is_market_open_fn=None):
    """
    Uptime: time since the most recent "Started" marker row (a row
    with empty Decision/Confidence/Price -- every book logs one of
    these on boot, worded slightly differently per book).

    Running/Idle/Down: "running" if the most recent row of ANY kind
    is fresher than a few scan cycles; for books with market hours
    (is_market_open_fn given), a stale log while the market is closed
    reads as "idle", not "down" -- that's expected behaviour, not a
    fault.
    """

    rows = _load_raw_rows(csv_path)

    if not rows:
        return {"running": False, "state": "down", "uptime": None, "last_trade": None}

    def parse_ts(row):
        return datetime.strptime(f"{row['Date']} {row['Time']}", "%Y-%m-%d %H:%M:%S")

    last_row_ts = parse_ts(rows[-1])

    started_rows = [
        row for row in rows
        if not row.get("Decision") and "Started" in (row.get("Message") or "")
    ]

    uptime_start = parse_ts(started_rows[-1]) if started_rows else parse_ts(rows[0])

    trade_rows = [row for row in rows if row.get("Decision") in ("BUY", "SELL")]
    last_trade_ts = parse_ts(trade_rows[-1]) if trade_rows else None

    staleness = datetime.now() - last_row_ts

    market_open = is_market_open_fn() if is_market_open_fn else True

    if staleness <= timedelta(seconds=max(scan_interval_seconds * 4, 180)):
        state = "running"
    elif not market_open:
        state = "idle"
    else:
        state = "down"

    return {
        "running": state == "running",
        "state": state,
        "uptime_start": uptime_start,
        "uptime_seconds": (datetime.now() - uptime_start).total_seconds(),
        "last_trade": last_trade_ts,
        "last_update": last_row_ts,
    }


def format_uptime(seconds):

    if seconds is None:
        return "—"

    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    if days:
        return f"{days}d {hours}h {minutes}m"

    if hours:
        return f"{hours}h {minutes}m"

    return f"{minutes}m"


def format_ago(dt):

    if dt is None:
        return "—"

    delta = datetime.now() - dt

    seconds = delta.total_seconds()

    if seconds < 60:
        return "just now"

    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"

    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"

    return f"{int(seconds // 86400)}d ago"


# ============================================================
# COMBINED VIEWS ACROSS BOOKS
# ============================================================

def combined_trades(book_defs, limit=None):
    """book_defs: [(book_key, label, report_module), ...]. Tags each
    trade with which book it came from and sorts newest-first across
    all of them together."""

    combined = []

    for key, label, report_module in book_defs:

        trades = report_module.load_trades()

        for trade in report_utils.full_trade_history(trades):

            trade = dict(trade)
            trade["book"] = label
            trade["book_key"] = key

            combined.append(trade)

    combined.sort(key=lambda t: (t["date"], t["time"]), reverse=True)

    return combined[:limit] if limit else combined


def combined_open_positions(book_defs):
    """book_defs: [(book_key, label, portfolio_module), ...]."""

    combined = []

    for key, label, portfolio_module in book_defs:

        try:
            positions = portfolio_module.get_positions()
        except Exception:
            positions = {}

        for symbol, position in positions.items():

            combined.append({
                "book": label,
                "book_key": key,
                "symbol": symbol,
                "entry_price": float(position.get("entry_price", 0.0)),
                "quantity": float(position.get("quantity", 0.0)),
                "stop_loss": position.get("stop_loss"),
                "take_profit": position.get("take_profit"),
            })

    return combined


def combined_equity_curve(book_defs, point_limit=500):
    """
    Sums each book's equity curve onto a shared timeline. Books log
    at slightly different times, so each book's series is forward-
    filled onto the union of all timestamps (carry the last known
    value forward) rather than requiring exact timestamp alignment.
    """

    per_book_series = []

    all_timestamps = set()

    for key, label, report_module in book_defs:

        rows = report_module.load_equity_curve()

        series = {}

        for row in rows:

            ts = f"{row['Date']} {row['Time']}"
            series[ts] = float(row["TotalEquity"])

        per_book_series.append(series)
        all_timestamps.update(series.keys())

    if not all_timestamps:
        return []

    sorted_ts = sorted(all_timestamps)

    combined = []
    last_values = [None] * len(per_book_series)

    for ts in sorted_ts:

        total = 0.0
        have_any = False

        for i, series in enumerate(per_book_series):

            if ts in series:
                last_values[i] = series[ts]

            if last_values[i] is not None:
                total += last_values[i]
                have_any = True

        if have_any:
            combined.append({"label": ts, "equity": total})

    return combined[-point_limit:]


# ============================================================
# TOP MOVERS -- real 24h ticker data, crypto only (the only book
# whose exchange exposes broad 24h ticker data cheaply in one call)
# ============================================================

def get_top_movers(exchange_module, limit=5, min_quote_volume=1_000_000):

    try:

        tickers = exchange_module.exchange.fetch_tickers()

    except Exception:
        return {"gainers": [], "losers": []}

    usdt_pairs = [
        (symbol, data) for symbol, data in tickers.items()
        if symbol.endswith("/USDT")
        and data.get("percentage") is not None
        and (data.get("quoteVolume") or 0) >= min_quote_volume
    ]

    ranked = sorted(usdt_pairs, key=lambda item: item[1]["percentage"], reverse=True)

    def _fmt(entries):
        return [
            {
                "symbol": symbol,
                "price": data.get("last"),
                "change_pct": data["percentage"],
            }
            for symbol, data in entries
        ]

    return {
        "gainers": _fmt(ranked[:limit]),
        "losers": _fmt(list(reversed(ranked))[:limit]),
    }


# ============================================================
# NOTIFICATIONS -- real events pulled from trade logs (stop-losses,
# take-profits, "Started" restarts), not a fabricated alert feed
# ============================================================

def get_notifications(book_defs, lookback_hours=24, limit=8):
    """book_defs: [(book_key, label, report_module), ...]."""

    cutoff = datetime.now() - timedelta(hours=lookback_hours)

    events = []

    for key, label, report_module in book_defs:

        rows = _load_raw_rows(report_module.TRADE_LOG)

        for row in rows:

            try:
                ts = datetime.strptime(f"{row['Date']} {row['Time']}", "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue

            if ts < cutoff:
                continue

            message = row.get("Message") or ""

            if row.get("Decision") == "SELL" and "STOP LOSS" in message:

                pnl = message.split("P&L=")[1] if "P&L=" in message else "?"

                events.append({
                    "ts": ts, "book": label,
                    "text": f"{row['Symbol']} stopped out ({pnl})",
                    "kind": "loss",
                })

            elif row.get("Decision") == "SELL" and "TAKE PROFIT" in message:

                pnl = message.split("P&L=")[1] if "P&L=" in message else "?"

                events.append({
                    "ts": ts, "book": label,
                    "text": f"{row['Symbol']} hit take-profit (+{pnl})",
                    "kind": "win",
                })

            elif "Started" in message and not row.get("Decision"):

                events.append({
                    "ts": ts, "book": label,
                    "text": f"{label} bot (re)started",
                    "kind": "info",
                })

    events.sort(key=lambda e: e["ts"], reverse=True)

    return events[:limit]


# ============================================================
# MARKET SIGNAL -- a REAL, disclosed technical read, standing in for
# the "AI Market Sentiment" widget until the actual AI/News tier
# exists. Not AI, not fabricated -- a plain composite of two things
# Atlas already computes: how many recently-scanned crypto symbols
# are in a bullish EMA trend, and the live BTC volatility regime
# reading. Labelled as a "Market Signal", not "AI", on purpose.
# ============================================================

def get_market_signal(exchange_module, symbols_limit=40):

    try:

        from indicators import Indicators

        symbols = exchange_module.get_markets()[:symbols_limit]

        bullish = 0
        counted = 0

        for symbol in symbols:

            try:
                candles = exchange_module.get_candles(symbol)
            except Exception:
                continue

            if not candles or len(candles) < 60:
                continue

            closes = [float(c[4]) for c in candles]

            ema_fast = Indicators.ema_fast(closes)
            ema_slow = Indicators.ema_slow(closes)

            counted += 1

            if ema_fast > ema_slow:
                bullish += 1

        if counted == 0:
            return None

        bullish_pct = bullish / counted * 100

        if bullish_pct >= 60:
            label = "Bullish"
        elif bullish_pct <= 40:
            label = "Bearish"
        else:
            label = "Neutral"

        return {
            "label": label,
            "score": round(bullish_pct),
            "bullish_pct": bullish_pct,
            "bearish_pct": 100 - bullish_pct,
            "sample_size": counted,
        }

    except Exception:
        return None
