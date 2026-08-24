"""
=========================================
ATLAS AI
Multi-Timeframe Confirmation -- Train/Test Validation
=========================================

OPTIMIZATION_LOG.md 2026-08-23: a proper train/test check (this
script) showed 1h confirmation's full-window win was partly illusory
-- it collapsed in one window's held-out test slice. This version
also tests 4h as a candidate replacement/addition -- a slower,
smoother trend signal that may be less prone to the same short-term
whipsaw that likely explains 1h's fragility. Train/test discipline is
built in from the start this time, not added after the fact.
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

        split_ts = optimize.compute_split_ts(cache)

        for tag, kwargs in [
            ("No filter", {}),
            ("1h confirmation", {"require_htf_confirmation": True, "htf": "1h"}),
            ("4h confirmation", {"require_htf_confirmation": True, "htf": "4h"}),
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
    print("HTF CONFIRMATION -- TRAIN/TEST VALIDATION (per window, last 25% of trades held out)")
    print("=" * 110)
    print(tabulate(
        rows,
        headers=["Window", "Config", "Train N", "Train WR", "Train Exp", "Test N", "Test WR", "Test Exp"],
    ))
    print("=" * 110)


if __name__ == "__main__":
    run()
