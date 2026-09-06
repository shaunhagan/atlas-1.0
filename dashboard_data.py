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


def combined_equity_curve(book_defs, point_limit=None):
    """
    Sums each book's equity curve onto a shared timeline. Books log
    at slightly different times, so each book's series is forward-
    filled onto the union of all timestamps (carry the last known
    value forward) rather than requiring exact timestamp alignment.

    point_limit=None returns the full history -- needed for an
    accurate all-time max-drawdown figure and so the chart's "ALL"
    range control actually shows everything, not a truncated tail.
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

    return combined[-point_limit:] if point_limit else combined


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


# ============================================================
# EXCHANGE CONNECTIVITY -- a real, live check, replacing what used
# to be a hardcoded "Connected" label. Best-effort: any exception
# (timeout, auth, network) reads as disconnected rather than crashing
# the page render.
# ============================================================

def check_exchange_connectivity(exchange_module):

    try:
        exchange_module.now_ms()
        return True
    except Exception:
        return False


# ============================================================
# STRATEGY HEALTH -- derived entirely from real trade/equity data,
# comparing a book's recent trades against its own all-time baseline.
# Thresholds are documented here, not hidden -- this is meant to be
# checkable, not a black box.
# ============================================================

RECENT_TRADE_WINDOW = 20


def compute_strategy_health(report_module):

    trades = report_module.load_trades()
    closed, wins, losses = report_module.summarise_trades(trades)
    equity_rows = report_module.load_equity_curve()

    if len(closed) < 10:

        return {
            "status": "watch",
            "title": "Gathering Data",
            "detail": f"Only {len(closed)} closed trades so far -- too few to read a health trend from yet.",
        }

    recent = closed[-RECENT_TRADE_WINDOW:]
    recent_wins = [t for t in recent if t["pnl"] > 0]

    recent_expectancy = sum(t["pnl"] for t in recent) / len(recent)
    recent_win_rate = len(recent_wins) / len(recent) * 100

    overall_expectancy = sum(t["pnl"] for t in closed) / len(closed)
    overall_win_rate = (len(wins) / len(closed) * 100) if closed else 0.0

    overall_drawdown = report_module.max_drawdown(equity_rows)

    # "Recent" drawdown window: the tail of the equity curve roughly
    # matching how far back RECENT_TRADE_WINDOW trades likely spans.
    # Approximate on purpose -- this is a health signal, not a precise
    # backtest metric.
    recent_equity_rows = equity_rows[-500:] if len(equity_rows) > 500 else equity_rows
    recent_drawdown = report_module.max_drawdown(recent_equity_rows)

    issues = []

    if recent_expectancy < 0:
        issues.append("Recent trades running net negative")

    if recent_win_rate < overall_win_rate - 10:
        issues.append("Win rate deteriorating vs all-time average")

    if overall_drawdown > 0 and recent_drawdown >= overall_drawdown * 0.85:
        issues.append("Drawdown elevated")

    if not issues:
        status, title = "good", "Good"
    elif len(issues) == 1:
        status, title = "watch", "Watch"
    else:
        status, title = "poor", "Poor"

    return {
        "status": status,
        "title": title,
        "detail": " · ".join(issues) if issues else "Recent performance in line with the book's own history.",
        "recent_expectancy": recent_expectancy,
        "recent_win_rate": recent_win_rate,
        "overall_expectancy": overall_expectancy,
        "overall_win_rate": overall_win_rate,
        "recent_drawdown": recent_drawdown,
        "overall_drawdown": overall_drawdown,
    }


# ============================================================
# SIGNAL REASONING -- "why did/would the bot trade this", computed
# live for currently open positions by re-running the SAME signal
# logic the live scanner uses. This is a CURRENT reading, not a
# stored record of the reasoning at the moment of original entry
# (that was never persisted to the trade log) -- labelled as such
# in the UI. Real numbers from a real re-evaluation, never fabricated.
# ============================================================

def trend_engine_reasoning(exchange_module, symbol, min_confidence):
    """For crypto and meme -- both run the same EMA/RSI/MACD/volume
    SignalEngine, just with different thresholds."""

    from indicators import Indicators
    from signals import SignalEngine

    try:

        ticker = exchange_module.get_ticker(symbol)
        candles = exchange_module.get_candles(symbol)

        if not candles or len(candles) < 60:
            return None

        price = float(ticker.get("last") or candles[-1][4])

        closes = [float(c[4]) for c in candles]
        volumes = [float(c[5]) for c in candles]
        highs = [float(c[2]) for c in candles]
        lows = [float(c[3]) for c in candles]

        ema_fast = Indicators.ema_fast(closes)
        ema_slow = Indicators.ema_slow(closes)
        rsi = Indicators.rsi(closes)
        macd, macd_signal, histogram = Indicators.macd(closes)
        volume_ratio = Indicators.volume_ratio(volumes)
        atr = Indicators.atr(highs, lows, closes)

        result = SignalEngine.evaluate(
            price, ema_fast, ema_slow, rsi, macd, macd_signal, histogram,
            volume_ratio, min_confidence=min_confidence,
        )

        return {
            "symbol": symbol,
            "decision": result["decision"],
            "confidence": result["confidence"],
            "reasons": result["reasons"],
            "price": price,
            "atr": atr,
            "rsi": rsi,
        }

    except Exception:
        return None


def mean_reversion_reasoning(exchange_module, symbol):
    """For stocks -- the live Bollinger Band + RSI mean-reversion
    entry, mirroring stock_scanner.analyse_market()'s logic exactly."""

    from indicators import Indicators
    from config import BOLLINGER_PERIOD, BOLLINGER_STDDEV, MEANREV_RSI_OVERSOLD

    try:

        ticker = exchange_module.get_ticker(symbol)
        candles = exchange_module.get_candles(symbol)

        if not candles or len(candles) < 60:
            return None

        price = float(ticker.get("last") or candles[-1][4])
        closes = [float(c[4]) for c in candles]
        highs = [float(c[2]) for c in candles]
        lows = [float(c[3]) for c in candles]

        rsi = Indicators.rsi(closes)
        atr = Indicators.atr(highs, lows, closes)
        upper, middle, lower = Indicators.bollinger_bands(closes, BOLLINGER_PERIOD, BOLLINGER_STDDEV)

        fired = (
            rsi == rsi and lower == lower
            and price <= lower and rsi < MEANREV_RSI_OVERSOLD
        )

        reasons = []

        if fired:
            reasons.append(f"Price at/below lower Bollinger Band ({lower:.4f})")
            reasons.append(f"RSI {rsi:.1f} confirms oversold (< {MEANREV_RSI_OVERSOLD})")
        else:
            if lower == lower and price > lower:
                reasons.append(f"Price {price:.4f} is above the lower band ({lower:.4f}) -- not oversold enough")
            if rsi == rsi and rsi >= MEANREV_RSI_OVERSOLD:
                reasons.append(f"RSI {rsi:.1f} is not below the {MEANREV_RSI_OVERSOLD} oversold threshold")

        return {
            "symbol": symbol,
            "decision": "BUY" if fired else "HOLD",
            "confidence": 75 if fired else 0,
            "reasons": reasons,
            "price": price,
            "atr": atr,
            "rsi": rsi,
        }

    except Exception:
        return None
