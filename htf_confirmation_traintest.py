"""
=========================================
ATLAS AI
Multi-Timeframe Confirmation -- Train/Test Validation
=========================================

htf_confirmation_test.py showed 1h confirmation beating the volatility
filter on full-window aggregates across 3 windows, but without the
held-out-period discipline optimize.py used for the exit-parameter
sweep. This re-checks it: within each window, does the improvement
hold on the last 25% of trades (by entry time), not just the full
window average?
"""

from tabulate import tabulate

import backtest
import optimize


VALIDATION_SYMBOL_LIMIT = 40

WINDOWS = [
    ("Primary (last 30d)", 0),
    ("Second (35-65d ago)", 35),
    ("Third (65-95d ago)", 65),
]


def run():

    symbols = backtest.exchange.get_markets()[:VALIDATION_SYMBOL_LIMIT]

    rows = []

    for label, end_days_ago in WINDOWS:

        print(f"\n--- {label} ---")

        cache = {}

        for symbol in symbols:
            cache[symbol] = backtest.fetch_history(
                symbol, days=30, end_days_ago=end_days_ago,
            )

        split_ts = backtest.exchange.now_ms() - int(
            (end_days_ago + backtest.BACKTEST_DAYS * optimize.TEST_FRACTION)
            * 24 * 60 * 60 * 1000
        )

        for tag, kwargs in [
            ("No filter", {}),
            ("1h confirmation", {"require_htf_confirmation": True}),
        ]:

            trades = backtest.run_backtest(
                symbols=symbols, candle_cache=cache, verbose=False, **kwargs,
            )

            train, test = optimize.split_trades(trades, split_ts)

            train_stats = optimize.summarise(train)
            test_stats = optimize.summarise(test)

            rows.append([
                label, tag,
                train_stats["count"], f"{train_stats['win_rate']:.1f}%", f"{train_stats['expectancy']:+.3f}%",
                test_stats["count"], f"{test_stats['win_rate']:.1f}%", f"{test_stats['expectancy']:+.3f}%",
            ])

    print("\n" + "=" * 110)
    print("1H CONFIRMATION -- TRAIN/TEST VALIDATION (per window, last 25% of trades held out)")
    print("=" * 110)
    print(tabulate(
        rows,
        headers=["Window", "Config", "Train N", "Train WR", "Train Exp", "Test N", "Test WR", "Test Exp"],
    ))
    print("=" * 110)


if __name__ == "__main__":
    run()
