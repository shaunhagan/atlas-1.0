"""
=========================================
ATLAS AI
Stock Mean-Reversion -- Parameter Robustness Check
=========================================

The BB(20,2)/RSI<30 combination replicated positive test-period
expectancy across two independent 90-day windows -- but that's one
specific parameter combination. Before trusting it's a real effect
and not a lucky combination, check whether nearby parameter choices
(BB width, RSI threshold) tell the same story on both windows, using
the already-cached candle data from stock_meanrev_traintest.py and
stock_meanrev_window2.py (no new fetches needed).
"""

from tabulate import tabulate

import stock_backtest
import stock_meanrev_backtest
import optimize


WINDOWS = [
    ("Window 1 (last 90d)", 0),
    ("Window 2 (90-180d ago)", 90),
]

BOLLINGER_STDDEV_GRID = [1.5, 2.0, 2.5]

RSI_OVERSOLD_GRID = [25, 30, 35]


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

        for stddev in BOLLINGER_STDDEV_GRID:

            for rsi_th in RSI_OVERSOLD_GRID:

                trades = stock_meanrev_backtest.run_backtest(
                    symbols=symbols, days=90, candle_cache=candle_cache,
                    verbose=False,
                    bollinger_stddev=stddev, rsi_oversold=rsi_th,
                )

                train, test = optimize.split_trades(trades, split_ts)

                train_stats = optimize.summarise(train)
                test_stats = optimize.summarise(test)

                rows.append([
                    window_label, f"BB={stddev}", f"RSI<{rsi_th}",
                    train_stats["count"], f"{train_stats['expectancy']:+.3f}%",
                    test_stats["count"], f"{test_stats['expectancy']:+.3f}%",
                ])

    print("\n" + "=" * 110)
    print("STOCK MEAN-REVERSION -- PARAMETER ROBUSTNESS ACROSS BOTH WINDOWS")
    print("=" * 110)
    print(tabulate(
        rows,
        headers=["Window", "BB stddev", "RSI threshold", "Train N", "Train Exp", "Test N", "Test Exp"],
    ))
    print("=" * 110)


if __name__ == "__main__":
    main()
