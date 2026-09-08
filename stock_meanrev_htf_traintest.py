"""
=========================================
ATLAS AI
Stock Mean-Reversion -- Higher Timeframe (15m) Test
=========================================

Every strategy tried for stocks so far (trend engine, mean reversion,
VWAP+gap) shares one assumption: 5-minute bars. Large-cap, heavily-
arbitraged equities may simply have too little exploitable signal at
5-minute granularity (dominated by institutional HFT noise) --
worth testing whether a coarser bar (15m) changes the picture before
concluding no easily-exploitable technical edge exists at all
(STOCK_OPTIMIZATION_LOG.md, 2026-09-08).

Reuses stock_meanrev_backtest's simulate_symbol/run_backtest exactly
(same BB+RSI entry, same ATR bracket exit) -- only the underlying
candle data changes, via stock_exchange.get_historical_candles' new
optional timeframe_minutes override (defaults preserve the live
scanner's 5m behaviour untouched; this is research-only usage).
"""

from pathlib import Path

import pandas as pd
from tabulate import tabulate

import stock_backtest
import stock_meanrev_backtest
import optimize
from stock_exchange import exchange


TIMEFRAME_MINUTES = 15

VALIDATION_DAYS = 90

DATA_FOLDER = Path("stock_backtest_data_15m")
DATA_FOLDER.mkdir(exist_ok=True)


def fetch_history_15m(symbol, days=VALIDATION_DAYS):

    cache_file = DATA_FOLDER / f"{symbol}_{days}d.csv"

    if cache_file.exists():
        return pd.read_csv(cache_file).values.tolist()

    end_ms = exchange.now_ms()
    since = end_ms - days * 24 * 60 * 60 * 1000

    all_candles = []

    while True:

        batch = exchange.get_historical_candles(
            symbol, since=since, limit=1000, timeframe_minutes=TIMEFRAME_MINUTES,
        )

        if not batch:
            break

        all_candles.extend(batch)

        if len(batch) < 1000:
            break

        since = batch[-1][0] + 1

        if since >= end_ms:
            break

    all_candles = [c for c in all_candles if c[0] <= end_ms]

    if not all_candles:
        return []

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df.drop_duplicates(subset="timestamp", inplace=True)
    df.to_csv(cache_file, index=False)

    return df.values.tolist()


def main():

    symbols = stock_backtest.exchange.get_markets()[:stock_backtest.SYMBOL_LIMIT]

    print(f"Fetching {VALIDATION_DAYS} days of {TIMEFRAME_MINUTES}m history for {len(symbols)} symbols...\n")

    candle_cache = {}

    for index, symbol in enumerate(symbols, start=1):

        candle_cache[symbol] = fetch_history_15m(symbol, days=VALIDATION_DAYS)

        print(f"[{index}/{len(symbols)}] {symbol}: {len(candle_cache[symbol])} candles")

    trades = stock_meanrev_backtest.run_backtest(
        symbols=symbols, days=VALIDATION_DAYS, candle_cache=candle_cache, verbose=True,
    )

    stock_meanrev_backtest.print_backtest_report(trades)

    split_ts = optimize.compute_split_ts(candle_cache)

    train, test = optimize.split_trades(trades, split_ts)

    train_stats = optimize.summarise(train)
    test_stats = optimize.summarise(test)

    print("\n" + "=" * 70)
    print(f"STOCK MEAN-REVERSION -- {TIMEFRAME_MINUTES}m TRAIN/TEST VALIDATION")
    print("=" * 70)
    print(tabulate(
        [
            ["TRAIN", train_stats["count"], f"{train_stats['win_rate']:.1f}%", f"{train_stats['expectancy']:+.3f}%"],
            ["TEST (held out)", test_stats["count"], f"{test_stats['win_rate']:.1f}%", f"{test_stats['expectancy']:+.3f}%"],
        ],
        headers=["Split", "Trades", "Win Rate", "Expectancy/Trade"],
    ))
    print("=" * 70)


if __name__ == "__main__":
    main()
