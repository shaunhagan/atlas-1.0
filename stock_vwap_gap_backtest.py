"""
=========================================
ATLAS AI
Stock VWAP + Gap-Pullback Backtester (research)
=========================================

Five independent regime/filter hypotheses failed to stabilise mean
reversion's live performance -- the "good" window keeps swapping with
the "bad" one purely from the calendar moving forward
(STOCK_OPTIMIZATION_LOG.md, 2026-09-08). Rather than retune that same
family further, this tests a structurally different, externally-
evidenced pattern: buying the first pullback to the session VWAP
after a gap-up open, in the first part of the trading day. Real
research backing (documented ~65% success rate for this specific
setup on >3% gap-ups in the first 90 minutes) -- not another guess.

Mechanics:
- Session-anchored VWAP, reset every trading day (not a rolling
  window across days -- this is specifically an intraday reference
  level, using IEX bars converted to US/Eastern).
- Gap = (today's 09:30 open - prior session's close) / prior close.
  Only trading days with gap_pct >= MIN_GAP_PCT are considered.
- Entry window: the first ENTRY_WINDOW_MINUTES of the session only.
- Entry: the first candle where price, having opened above VWAP,
  touches back down to at/below VWAP (the "pullback").
- Same ATR-based bracket exit/position mechanics as every other
  backtester in this project -- only the entry signal differs, so
  this is an apples-to-apples comparison, not a confound of also
  changing risk management.

Long-only, matching the rest of this project.
"""

from datetime import time as dt_time

import pandas as pd
from tabulate import tabulate

import stock_backtest
from stock_backtest import exchange, fetch_history, SYMBOL_LIMIT, BACKTEST_DAYS
from indicators import Indicators
from config import (
    STOCK_ATR_STOP_MULTIPLIER,
    STOCK_RISK_REWARD_RATIO,
    STOCK_TRADING_FRICTION_PCT,
    ATR_PERIOD,
)


MIN_GAP_PCT = 2.0

ENTRY_WINDOW_MINUTES = 90

SESSION_OPEN = dt_time(9, 30)


def _build_session_frame(candles):
    """Adds US/Eastern datetime, trading-date, session VWAP, gap %,
    and an entry-eligibility flag to a DataFrame of 5m candles."""

    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])

    df["dt"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_convert("America/New_York")
    df["date"] = df["dt"].dt.date
    df["time"] = df["dt"].dt.time

    # Regular session only (09:30-16:00) -- drop pre/post-market bars,
    # which would otherwise distort VWAP and "today's open".
    session_mask = (df["time"] >= SESSION_OPEN) & (df["time"] <= dt_time(16, 0))
    df = df[session_mask].reset_index(drop=True)

    if df.empty:
        return df

    typical_price = (df["high"] + df["low"] + df["close"]) / 3

    df["cum_vol"] = df.groupby("date")["volume"].cumsum()
    df["cum_vol_price"] = (typical_price * df["volume"]).groupby(df["date"]).cumsum()

    df["vwap"] = df["cum_vol_price"] / df["cum_vol"].replace(0, pd.NA)

    session_open_price = df.groupby("date")["open"].transform("first")

    daily_close = df.groupby("date")["close"].last()
    prior_close = daily_close.shift(1)
    df["prior_close"] = df["date"].map(prior_close)

    df["gap_pct"] = (session_open_price - df["prior_close"]) / df["prior_close"] * 100

    session_start_dt = df.groupby("date")["dt"].transform("first")
    df["minutes_since_open"] = (df["dt"] - session_start_dt).dt.total_seconds() / 60

    return df


def simulate_symbol(
    symbol,
    candles,
    atr_stop_multiplier=STOCK_ATR_STOP_MULTIPLIER,
    risk_reward_ratio=STOCK_RISK_REWARD_RATIO,
    friction_pct=STOCK_TRADING_FRICTION_PCT,
    min_gap_pct=MIN_GAP_PCT,
    entry_window_minutes=ENTRY_WINDOW_MINUTES,
):

    df = _build_session_frame(candles)

    if df.empty or len(df) < ATR_PERIOD + 5:
        return []

    trades = []

    in_position = False
    entry_price = None
    stop_loss = None
    take_profit = None
    entry_ts = None

    was_above_vwap = {}

    highs = df["high"].tolist()
    lows = df["low"].tolist()
    closes = df["close"].tolist()

    for i in range(ATR_PERIOD, len(df)):

        row = df.iloc[i]

        if in_position:

            high, low = row["high"], row["low"]

            if low <= stop_loss:

                exit_fill = stop_loss * (1 - friction_pct)

                trades.append({
                    "symbol": symbol,
                    "pnl_pct": (exit_fill - entry_price) / entry_price * 100,
                    "reason": "STOP LOSS",
                    "confidence": None,
                    "entry_ts": entry_ts,
                })

                in_position = False

            elif high >= take_profit:

                exit_fill = take_profit * (1 - friction_pct)

                trades.append({
                    "symbol": symbol,
                    "pnl_pct": (exit_fill - entry_price) / entry_price * 100,
                    "reason": "TAKE PROFIT",
                    "confidence": None,
                    "entry_ts": entry_ts,
                })

                in_position = False

            continue

        date = row["date"]
        vwap = row["vwap"]
        price = row["close"]

        if pd.isna(vwap) or pd.isna(row["gap_pct"]):
            continue

        # Track whether this symbol has traded above VWAP yet today --
        # a "pullback" requires having been above it first.
        above_now = price > vwap

        if date not in was_above_vwap:
            was_above_vwap[date] = False

        pulled_back = was_above_vwap[date] and price <= vwap

        if above_now:
            was_above_vwap[date] = True

        if not pulled_back:
            continue

        if row["gap_pct"] < min_gap_pct:
            continue

        if row["minutes_since_open"] > entry_window_minutes:
            continue

        try:
            atr = Indicators.atr(
                highs[max(0, i - ATR_PERIOD):i + 1],
                lows[max(0, i - ATR_PERIOD):i + 1],
                closes[max(0, i - ATR_PERIOD):i + 1],
            )
        except Exception:
            continue

        if atr is None or pd.isna(atr) or atr <= 0:
            continue

        stop_distance = atr_stop_multiplier * atr

        fill_price = price * (1 + friction_pct)

        candidate_stop = fill_price - stop_distance

        if candidate_stop <= 0:
            continue

        entry_price = fill_price
        stop_loss = candidate_stop
        take_profit = fill_price + (risk_reward_ratio * stop_distance)
        entry_ts = int(row["timestamp"])

        in_position = True

    return trades


def run_backtest(
    symbol_limit=SYMBOL_LIMIT,
    days=BACKTEST_DAYS,
    symbols=None,
    candle_cache=None,
    verbose=True,
    **simulate_kwargs,
):

    if symbols is None:
        symbols = exchange.get_markets()[:symbol_limit]

    if verbose:
        print(f"VWAP+gap backtesting {len(symbols)} symbols over {days} days...\n")

    all_trades = []

    for index, symbol in enumerate(symbols, start=1):

        try:

            if candle_cache is not None and symbol in candle_cache:
                candles = candle_cache[symbol]
            else:
                candles = fetch_history(symbol, days)
                if candle_cache is not None:
                    candle_cache[symbol] = candles

            if len(candles) < 100:
                if verbose:
                    print(f"[{index}/{len(symbols)}] {symbol}: skipped (not enough history)")
                continue

            trades = simulate_symbol(symbol, candles, **simulate_kwargs)

            all_trades.extend(trades)

            if verbose:
                print(f"[{index}/{len(symbols)}] {symbol}: {len(candles)} candles, {len(trades)} trades")

        except Exception as error:

            if verbose:
                print(f"[{index}/{len(symbols)}] {symbol}: ERROR {error}")

    return all_trades


def print_backtest_report(trades):

    print()
    print("=" * 70)
    print("      ATLAS AI STOCKS - VWAP+GAP BACKTEST REPORT")
    print("=" * 70)

    if not trades:
        print("\nNo trades were generated.")
        return

    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]

    win_rate = len(wins) / len(trades) * 100
    avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0.0
    avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0.0
    expectancy = sum(t["pnl_pct"] for t in trades) / len(trades)

    print(f"\nTotal Trades     : {len(trades)}")
    print(f"Win Rate         : {win_rate:.1f}% ({len(wins)}W / {len(losses)}L)")
    print(f"Average Win      : {avg_win:+.2f}%")
    print(f"Average Loss     : {avg_loss:+.2f}%")
    print(f"Expectancy/Trade : {expectancy:+.3f}%")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    trades = run_backtest()
    print_backtest_report(trades)
