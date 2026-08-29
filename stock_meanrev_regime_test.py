"""
=========================================
ATLAS AI
Stock Mean-Reversion -- ADX Regime Gate Test
=========================================

STOCK_OPTIMIZATION_LOG.md 2026-08-29: the BB+RSI mean-reversion entry
was NOT a stable edge on its own -- train expectancy was negative
across every parameter combination in the most recent 90-day window,
positive across every combination 90-180 days ago. Matches the
external research that mean-reversion specifically fails in trending
regimes. This tests whether an ADX-based regime gate (skip entries
when the market is trending, not ranging) reconciles the two windows
-- i.e. does the "bad" window improve once trending periods within it
are filtered out, without destroying the "good" window's edge.
"""

from tabulate import tabulate

import stock_backtest
import stock_meanrev_backtest
import optimize


WINDOWS = [
    ("Window 1 (last 90d)", 0),
    ("Window 2 (90-180d ago)", 90),
]

MAX_ADX_GRID = [None, 30, 25, 20, 15]


def main():

    symbols = stock_backtest.exchange.get_markets()[:stock_backtest.SYMBOL_LIMIT]

    rows = []

    for window_label, end_days_ago in WINDOWS:

        print(f"\n--- {window_label} ---")

        candle_cache = {}

        for symbol in symbols:
            candle_cache[symbol] = stock_backtest.fetch_history(
                symbol, days=90, end_days_ago=end_days_ago,
            )

        split_ts = optimize.compute_split_ts(candle_cache)

        for max_adx in MAX_ADX_GRID:

            trades = stock_meanrev_backtest.run_backtest(
                symbols=symbols, days=90, candle_cache=candle_cache,
                verbose=False, max_adx=max_adx,
            )

            train, test = optimize.split_trades(trades, split_ts)

            train_stats = optimize.summarise(train)
            test_stats = optimize.summarise(test)

            label = f"ADX<{max_adx}" if max_adx is not None else "No gate"

            rows.append([
                window_label, label,
                train_stats["count"], f"{train_stats['expectancy']:+.3f}%",
                test_stats["count"], f"{test_stats['expectancy']:+.3f}%",
            ])

    print("\n" + "=" * 100)
    print("STOCK MEAN-REVERSION -- ADX REGIME GATE, BOTH WINDOWS")
    print("=" * 100)
    print(tabulate(
        rows,
        headers=["Window", "Gate", "Train N", "Train Exp", "Test N", "Test Exp"],
    ))
    print("=" * 100)


if __name__ == "__main__":
    main()
