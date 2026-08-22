"""
=========================================
ATLAS AI
Backtester
=========================================

Replays historical candles through the exact same Indicators /
SignalEngine used live, and exits each simulated trade with the
same ATR-based bracket (stop-loss / take-profit) paper_trader.py
uses. This answers the question live paper trading takes days to
answer: does the signal + exit combo have positive expectancy,
measured in minutes instead of waiting on real time.

Deliberately simplified vs the live bot: no shared-capital /
MAX_OPEN_TRADES contention is simulated (each symbol is evaluated
independently, one position at a time). It measures signal quality,
not portfolio-level equity curve. Results here validate/tune the
signal engine; the live bot still tells you how it behaves under
real capital constraints.
"""

import time
from pathlib import Path

import pandas as pd
from tabulate import tabulate

from config import (
    CANDLE_LIMIT,
    TIMEFRAME,
    ATR_STOP_MULTIPLIER,
    RISK_REWARD_RATIO,
    TRADING_FRICTION_PCT,
    EMA_FAST,
    EMA_SLOW,
)

from exchange import exchange
from indicators import Indicators
from signals import SignalEngine


BACKTEST_DAYS = 30

SYMBOL_LIMIT = 60

DATA_FOLDER = Path("backtest_data")
DATA_FOLDER.mkdir(exist_ok=True)


# ============================================================
# HISTORICAL DATA FETCH / CACHE
# ============================================================

def _cache_path(symbol, days=BACKTEST_DAYS, end_days_ago=0):

    safe_name = symbol.replace("/", "_")

    if end_days_ago:
        return DATA_FOLDER / f"{safe_name}_{days}d_end{end_days_ago}d.csv"

    return DATA_FOLDER / f"{safe_name}.csv"


def fetch_history(symbol, days=BACKTEST_DAYS, end_days_ago=0):
    """
    Fetch (or load cached) OHLCV history for one symbol.

    end_days_ago shifts the whole window back in time -- e.g.
    end_days_ago=35 fetches `days` days of history ending 35 days
    ago instead of ending now. Used to validate findings on a
    second, non-overlapping historical period. end_days_ago=0
    (default) preserves the original behaviour exactly.
    """

    cache_file = _cache_path(symbol, days, end_days_ago)

    if cache_file.exists():

        df = pd.read_csv(cache_file)

        return df.values.tolist()

    end_ms = exchange.now_ms() - end_days_ago * 24 * 60 * 60 * 1000

    since = end_ms - days * 24 * 60 * 60 * 1000

    all_candles = []

    while True:

        batch = exchange.get_historical_candles(
            symbol,
            since=since,
            limit=1000,
        )

        if not batch:
            break

        all_candles.extend(batch)

        if len(batch) < 1000:
            break

        since = batch[-1][0] + 1

        if since >= end_ms:
            break

        time.sleep(0.05)

    all_candles = [
        candle for candle in all_candles
        if candle[0] <= end_ms
    ]

    if not all_candles:
        return []

    df = pd.DataFrame(
        all_candles,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )

    df.drop_duplicates(subset="timestamp", inplace=True)

    df.to_csv(cache_file, index=False)

    return df.values.tolist()


# ============================================================
# HIGHER-TIMEFRAME TREND FILTER
# ============================================================

def build_htf_trend_filter(candles_5m, htf="1h"):
    """
    Resamples the already-fetched 5m candles up to a higher
    timeframe (no extra API calls) and returns a function
    htf_trend_ok(ts) -> bool: is that higher-timeframe EMA_FAST >
    EMA_SLOW as of the most recently COMPLETED higher-timeframe bar
    before ts?

    shift(1) before reindexing onto the 5m grid is what prevents
    lookahead bias -- a bar labelled H only becomes visible starting
    at H + one bar, matching what a live bot would actually know at
    that moment (the current higher-timeframe bar is still forming).
    """

    df = pd.DataFrame(
        candles_5m,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )

    df["dt"] = pd.to_datetime(df["timestamp"], unit="ms")

    indexed = df.set_index("dt")

    htf_closes = indexed["close"].resample(htf, label="left", closed="left").last()

    htf_closes = htf_closes.dropna()

    ema_fast_htf = htf_closes.ewm(span=EMA_FAST, adjust=False).mean()
    ema_slow_htf = htf_closes.ewm(span=EMA_SLOW, adjust=False).mean()

    trend_bullish = (ema_fast_htf > ema_slow_htf).shift(1)

    trend_by_ts = trend_bullish.reindex(indexed.index, method="ffill")

    trend_by_ms = dict(zip(df["timestamp"], trend_by_ts.values))

    def htf_trend_ok(ts):

        value = trend_by_ms.get(ts)

        if value is None or pd.isna(value):
            return True

        return bool(value)

    return htf_trend_ok


# ============================================================
# SIMULATE ONE SYMBOL
# ============================================================

def simulate_symbol(
    symbol,
    candles,
    atr_stop_multiplier=ATR_STOP_MULTIPLIER,
    risk_reward_ratio=RISK_REWARD_RATIO,
    friction_pct=TRADING_FRICTION_PCT,
    regime_ok_fn=None,
    require_htf_confirmation=False,
    htf="1h",
    **signal_kwargs,
):
    """
    Walk forward through history one candle at a time, replaying
    the live signal engine on a trailing CANDLE_LIMIT window, and
    record the outcome of every BUY signal using the same
    ATR-based bracket exit paper_trader.py uses live.

    atr_stop_multiplier/risk_reward_ratio and any signal threshold
    override (min_confidence, min_ema_spread_pct, min_macd_hist_pct,
    min_volume_ratio) can be overridden for parameter sweeps -- they
    default to the live config values.

    require_htf_confirmation gates new entries on this SAME symbol's
    own higher-timeframe trend (see build_htf_trend_filter) -- built
    internally from `candles` since it's the same series already
    available, no extra fetch needed.
    """

    htf_trend_ok = (
        build_htf_trend_filter(candles, htf)
        if require_htf_confirmation else None
    )

    trades = []

    in_position = False
    entry_price = None
    stop_loss = None
    take_profit = None
    entry_confidence = None

    for i in range(CANDLE_LIMIT, len(candles)):

        if in_position:

            candle = candles[i]

            high = candle[2]
            low = candle[3]

            # Conservative assumption: if one candle's range spans
            # both levels, the stop is assumed to hit first.
            if low <= stop_loss:

                exit_fill = stop_loss * (1 - friction_pct)

                trades.append({
                    "symbol": symbol,
                    "pnl_pct": (
                        (exit_fill - entry_price) / entry_price * 100
                    ),
                    "reason": "STOP LOSS",
                    "confidence": entry_confidence,
                    "entry_ts": entry_ts,
                })

                in_position = False

            elif high >= take_profit:

                exit_fill = take_profit * (1 - friction_pct)

                trades.append({
                    "symbol": symbol,
                    "pnl_pct": (
                        (exit_fill - entry_price) / entry_price * 100
                    ),
                    "reason": "TAKE PROFIT",
                    "confidence": entry_confidence,
                    "entry_ts": entry_ts,
                })

                in_position = False

            continue

        window = candles[i - CANDLE_LIMIT:i]

        closes = [candle[4] for candle in window]
        highs = [candle[2] for candle in window]
        lows = [candle[3] for candle in window]
        volumes = [candle[5] for candle in window]

        price = closes[-1]

        try:

            ema_fast = Indicators.ema_fast(closes)
            ema_slow = Indicators.ema_slow(closes)
            rsi = Indicators.rsi(closes)
            macd, signal, histogram = Indicators.macd(closes)
            volume_ratio = Indicators.volume_ratio(volumes)
            atr = Indicators.atr(highs, lows, closes)

        except Exception:
            continue

        if atr is None or pd.isna(atr) or atr <= 0:
            continue

        result = SignalEngine.evaluate(
            price,
            ema_fast,
            ema_slow,
            rsi,
            macd,
            signal,
            histogram,
            volume_ratio,
            **signal_kwargs,
        )

        if result["decision"] != "BUY":
            continue

        if regime_ok_fn is not None and not regime_ok_fn(candles[i][0]):
            continue

        if htf_trend_ok is not None and not htf_trend_ok(candles[i][0]):
            continue

        stop_distance = atr_stop_multiplier * atr

        fill_price = price * (1 + friction_pct)

        candidate_stop = fill_price - stop_distance

        if candidate_stop <= 0:
            continue

        entry_price = fill_price
        stop_loss = candidate_stop
        take_profit = fill_price + (risk_reward_ratio * stop_distance)
        entry_confidence = result["confidence"]
        entry_ts = candles[i][0]

        in_position = True

    return trades


# ============================================================
# RUN BACKTEST
# ============================================================

def run_backtest(
    symbol_limit=SYMBOL_LIMIT,
    days=BACKTEST_DAYS,
    symbols=None,
    candle_cache=None,
    verbose=True,
    **simulate_kwargs,
):
    """
    candle_cache: optional {symbol: candles} dict to reuse
    already-fetched history across sweep runs without re-reading
    from disk each time.
    """

    if symbols is None:
        symbols = exchange.get_markets()[:symbol_limit]

    if verbose:
        print(
            f"Backtesting {len(symbols)} symbols over "
            f"{days} days of {TIMEFRAME} candles...\n"
        )

    all_trades = []

    for index, symbol in enumerate(symbols, start=1):

        try:

            if candle_cache is not None and symbol in candle_cache:
                candles = candle_cache[symbol]
            else:
                candles = fetch_history(symbol, days)
                if candle_cache is not None:
                    candle_cache[symbol] = candles

            if len(candles) < CANDLE_LIMIT + 10:
                if verbose:
                    print(f"[{index}/{len(symbols)}] {symbol}: skipped (not enough history)")
                continue

            trades = simulate_symbol(symbol, candles, **simulate_kwargs)

            all_trades.extend(trades)

            if verbose:
                print(
                    f"[{index}/{len(symbols)}] {symbol}: "
                    f"{len(candles)} candles, {len(trades)} trades"
                )

        except Exception as error:

            if verbose:
                print(f"[{index}/{len(symbols)}] {symbol}: ERROR {error}")

    return all_trades


# ============================================================
# REPORT
# ============================================================

def print_backtest_report(trades):

    print()
    print("=" * 70)
    print("                  ATLAS AI - BACKTEST REPORT")
    print("=" * 70)

    if not trades:

        print("\nNo trades were generated.")
        return

    wins = [trade for trade in trades if trade["pnl_pct"] > 0]
    losses = [trade for trade in trades if trade["pnl_pct"] <= 0]

    win_rate = len(wins) / len(trades) * 100

    avg_win = (
        sum(trade["pnl_pct"] for trade in wins) / len(wins)
        if wins else 0.0
    )

    avg_loss = (
        sum(trade["pnl_pct"] for trade in losses) / len(losses)
        if losses else 0.0
    )

    expectancy = sum(trade["pnl_pct"] for trade in trades) / len(trades)

    print(f"\nTotal Trades     : {len(trades)}")
    print(f"Win Rate         : {win_rate:.1f}% ({len(wins)}W / {len(losses)}L)")
    print(f"Average Win      : {avg_win:+.2f}%")
    print(f"Average Loss     : {avg_loss:+.2f}%")
    print(f"Expectancy/Trade : {expectancy:+.3f}%")

    buckets = {}

    for trade in trades:

        floor = (trade["confidence"] // 10) * 10
        label = f"{floor}-{floor + 9}"

        buckets.setdefault(label, []).append(trade["pnl_pct"])

    rows = []

    for label in sorted(buckets, key=lambda item: int(item.split("-")[0])):

        pnls = buckets[label]

        bucket_win_rate = (
            sum(1 for pnl in pnls if pnl > 0) / len(pnls) * 100
        )

        rows.append([
            label,
            len(pnls),
            f"{bucket_win_rate:.1f}%",
            f"{sum(pnls) / len(pnls):+.3f}%",
        ])

    print("\nBy Confidence Bucket")
    print(tabulate(
        rows,
        headers=["Confidence", "Trades", "Win Rate", "Avg P&L%"],
    ))

    print()
    print("=" * 70)


if __name__ == "__main__":

    trades = run_backtest()
    print_backtest_report(trades)
