"""
=========================================
ATLAS AI
Stock Mean-Reversion Train/Test Validation
=========================================

The 30-day full-window result for stock_meanrev_backtest.py looked
promising (+0.850% expectancy) -- but that is exactly the trap that
already fooled the trend-engine research twice in STOCK_OPTIMIZATION_LOG.md
(looked good at 30 days, needed 90 to reveal the real picture). Same
90-day window and split discipline as stock_traintest.py, for a
like-for-like comparison against the trend engine's already-established
negative result.
"""

from tabulate import tabulate

import stock_backtest
import stock_meanrev_backtest
import optimize


VALIDATION_DAYS = 90


def main():

    symbols = stock_backtest.exchange.get_markets()[:stock_backtest.SYMBOL_LIMIT]

    print(f"Universe: {symbols}\n")
    print(f"Fetching {VALIDATION_DAYS} days of history for {len(symbols)} symbols...\n")

    candle_cache = {}

    for symbol in symbols:
        candle_cache[symbol] = stock_backtest.fetch_history(symbol, days=VALIDATION_DAYS)

    trades = stock_meanrev_backtest.run_backtest(
        symbols=symbols, days=VALIDATION_DAYS, candle_cache=candle_cache, verbose=True,
    )

    stock_meanrev_backtest.print_backtest_report(trades)

    split_ts = optimize.compute_split_ts(candle_cache)

    train, test = optimize.split_trades(trades, split_ts)

    train_stats = optimize.summarise(train)
    test_stats = optimize.summarise(test)

    print("\n" + "=" * 70)
    print("STOCK MEAN-REVERSION TRAIN/TEST VALIDATION (90 days)")
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
