"""
=========================================
ATLAS AI
Stock Backtest -- Train/Test Validation
=========================================

The first full-window stock backtest looked promising (+1.511%
expectancy), but crypto's research trail showed full-window
aggregates without a held-out split can be misleading or overfit
(OPTIMIZATION_LOG.md, 2026-08-18 ATR=20 rejection; 2026-08-23 split_ts
bug). Checking properly before trusting this: does the result hold up
on the last 25% of trades (by entry time), not seen during any
tuning (there's no tuning here yet -- this is just checking the raw
signal engine's out-of-sample stability first).

Reuses optimize.py's compute_split_ts/split_trades directly -- they're
generic over any candle_cache/trades shape, not crypto-specific.
"""

from tabulate import tabulate

import stock_backtest
import optimize


VALIDATION_SYMBOL_LIMIT = stock_backtest.SYMBOL_LIMIT


def run():

    symbols = stock_backtest.exchange.get_markets()[:VALIDATION_SYMBOL_LIMIT]

    print(f"Loading cached history for {len(symbols)} symbols...")

    cache = {}

    for symbol in symbols:
        cache[symbol] = stock_backtest.fetch_history(symbol)

    split_ts = optimize.compute_split_ts(cache)

    trades = stock_backtest.run_backtest(
        symbols=symbols, candle_cache=cache, verbose=False,
    )

    train, test = optimize.split_trades(trades, split_ts)

    train_stats = optimize.summarise(train)
    test_stats = optimize.summarise(test)

    print("\n" + "=" * 80)
    print("STOCK BACKTEST -- TRAIN/TEST VALIDATION (last 25% of trades held out)")
    print("=" * 80)
    print(tabulate(
        [
            ["Train", train_stats["count"], f"{train_stats['win_rate']:.1f}%", f"{train_stats['expectancy']:+.3f}%"],
            ["Test (held out)", test_stats["count"], f"{test_stats['win_rate']:.1f}%", f"{test_stats['expectancy']:+.3f}%"],
        ],
        headers=["Split", "Trades", "Win Rate", "Expectancy/Trade"],
    ))
    print("=" * 80)


if __name__ == "__main__":
    run()
