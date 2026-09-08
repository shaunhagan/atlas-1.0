"""
=========================================
ATLAS AI
Stock Mean-Reversion -- Minimum Price Filter Test
=========================================

Four regime hypotheses (ADX, SPY volatility, SPY volatility+trend, SPY
trend direction) all failed to explain the window-to-window variance
in mean reversion's live performance (STOCK_OPTIMIZATION_LOG.md,
2026-08-29/30). This tests a different kind of hypothesis: not WHEN
the strategy struggles, but WHICH SYMBOLS -- sub-$5 stocks (PDSB,
ATER, PLUG, NVD, NIO, KEEL, TSLG...) behave more like meme coins than
blue-chip equities (thin books, speculative retail-driven moves), and
might be diluting or destabilising the mean-reversion edge on higher-
quality names. Uses the symbol's own price at the start of each cached
window (not today's live price) to avoid look-ahead bias.
"""

from tabulate import tabulate

import stock_backtest
import stock_meanrev_backtest
import optimize


WINDOWS = [
    ("Window 1 (last 90d)", 0),
    ("Window 2 (90-180d ago)", 90),
]

MIN_PRICE_GRID = [0, 5, 10, 20]


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

        for min_price in MIN_PRICE_GRID:

            if min_price > 0:

                filtered_symbols = [
                    s for s in symbols
                    if candle_cache.get(s) and candle_cache[s][0][4] >= min_price
                ]

            else:
                filtered_symbols = symbols

            trades = stock_meanrev_backtest.run_backtest(
                symbols=filtered_symbols, days=90, candle_cache=candle_cache,
                verbose=False,
            )

            train, test = optimize.split_trades(trades, split_ts)

            train_stats = optimize.summarise(train)
            test_stats = optimize.summarise(test)

            rows.append([
                window_label, f"${min_price}+" if min_price else "No filter",
                len(filtered_symbols),
                train_stats["count"], f"{train_stats['expectancy']:+.3f}%",
                test_stats["count"], f"{test_stats['expectancy']:+.3f}%",
            ])

    print("\n" + "=" * 110)
    print("STOCK MEAN-REVERSION -- MINIMUM PRICE FILTER, BOTH WINDOWS")
    print("=" * 110)
    print(tabulate(
        rows,
        headers=["Window", "Min Price", "Symbols", "Train N", "Train Exp", "Test N", "Test Exp"],
    ))
    print("=" * 110)


if __name__ == "__main__":
    main()
