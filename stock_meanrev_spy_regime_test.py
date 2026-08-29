"""
=========================================
ATLAS AI
Stock Mean-Reversion -- SPY Volatility Regime Gate Test
=========================================

Per-symbol trend strength (ADX) did not explain the difference between
mean reversion's good window (90-180d ago) and bad window (last 90d)
-- see STOCK_OPTIMIZATION_LOG.md 2026-08-29, rejected. This tries a
market-wide signal instead: SPY realised volatility, using the exact
same build_regime_filters() already built and validated-elsewhere in
this project (crypto's live BTC filter, stocks' already-tested-on-the-
trend-engine SPY filter). Mean reversion classically prefers calm,
low-noise conditions -- worth checking whether that holds here before
giving up on regime-gating this strategy entirely.
"""

from tabulate import tabulate

import stock_backtest
import stock_meanrev_backtest
import optimize
from regime_filter_test import build_regime_filters, VOLATILITY_THRESHOLD_PCT


WINDOWS = [
    ("Window 1 (last 90d)", 0),
    ("Window 2 (90-180d ago)", 90),
]


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

        spy_candles = candle_cache.get("SPY") or stock_backtest.fetch_history(
            "SPY", days=90, end_days_ago=end_days_ago,
        )

        volatility_only, volatility_and_trend = build_regime_filters(
            spy_candles, VOLATILITY_THRESHOLD_PCT,
        )

        split_ts = optimize.compute_split_ts(candle_cache)

        configs = [
            ("No filter", None),
            ("SPY volatility only", volatility_only),
            ("SPY volatility + trend", volatility_and_trend),
        ]

        for label, regime_fn in configs:

            trades = stock_meanrev_backtest.run_backtest(
                symbols=symbols, days=90, candle_cache=candle_cache,
                verbose=False, regime_ok_fn=regime_fn,
            )

            train, test = optimize.split_trades(trades, split_ts)

            train_stats = optimize.summarise(train)
            test_stats = optimize.summarise(test)

            rows.append([
                window_label, label,
                train_stats["count"], f"{train_stats['expectancy']:+.3f}%",
                test_stats["count"], f"{test_stats['expectancy']:+.3f}%",
            ])

    print("\n" + "=" * 100)
    print("STOCK MEAN-REVERSION -- SPY VOLATILITY REGIME GATE, BOTH WINDOWS")
    print("=" * 100)
    print(tabulate(
        rows,
        headers=["Window", "Gate", "Train N", "Train Exp", "Test N", "Test Exp"],
    ))
    print("=" * 100)


if __name__ == "__main__":
    main()
