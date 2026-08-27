"""
=========================================
ATLAS AI
Stock Train/Test Validation (post symbol-universe fix)
=========================================

Re-runs the held-out validation from STOCK_OPTIMIZATION_LOG.md against
the corrected, volume-ranked symbol universe (get_markets() previously
sorted alphabetically -- fixed 2026-08-27). Every prior "no validated
edge" conclusion in that log was reached on an arbitrary early-alphabet
symbol set, not real liquid stocks, so this needs re-checking before
trusting that conclusion.

90-day window, same as the prior (universe-flawed) validation used,
for a like-for-like comparison.
"""

from tabulate import tabulate

import stock_backtest
import optimize


VALIDATION_DAYS = 90


def main():

    symbols = stock_backtest.exchange.get_markets()[:stock_backtest.SYMBOL_LIMIT]

    print(f"Universe: {symbols}\n")
    print(f"Fetching {VALIDATION_DAYS} days of history for {len(symbols)} symbols...\n")

    candle_cache = {}

    for symbol in symbols:
        candle_cache[symbol] = stock_backtest.fetch_history(symbol, days=VALIDATION_DAYS)

    trades = stock_backtest.run_backtest(
        symbols=symbols, days=VALIDATION_DAYS, candle_cache=candle_cache, verbose=True,
    )

    stock_backtest.print_backtest_report(trades)

    split_ts = optimize.compute_split_ts(candle_cache)

    train, test = optimize.split_trades(trades, split_ts)

    train_stats = optimize.summarise(train)
    test_stats = optimize.summarise(test)

    print("\n" + "=" * 70)
    print("STOCK TRAIN/TEST VALIDATION -- CORRECTED (volume-ranked) UNIVERSE")
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
