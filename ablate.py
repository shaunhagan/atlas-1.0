"""
=========================================
ATLAS AI
Signal Component Ablation
=========================================

The exit-parameter sweep (optimize.py) found the current live config
already near-optimal in that space (see OPTIMIZATION_LOG.md,
2026-08-18). This tests the other half of the problem: does each
individual scoring component in signals.py actually contribute
positive out-of-sample expectancy, or is one of them dead weight (or
actively harmful)?

Same train/test discipline as optimize.py: every comparison is judged
on the held-out test period, not the full period, to avoid the
overfitting trap already caught once today.
"""

from tabulate import tabulate

import backtest
import optimize


ABLATION_SYMBOL_LIMIT = 30

COMPONENTS = [
    "use_trend",
    "use_rsi",
    "use_macd",
    "use_momentum",
    "use_volume",
    "use_chop_gate",
]


def run_ablation(symbol_limit=ABLATION_SYMBOL_LIMIT):

    all_symbols = backtest.exchange.get_markets()[:symbol_limit]

    split_ts = backtest.exchange.now_ms() - int(
        backtest.BACKTEST_DAYS * optimize.TEST_FRACTION * 24 * 60 * 60 * 1000
    )

    print(f"Loading cached history for {len(all_symbols)} symbols...")

    candle_cache = {}

    for symbol in all_symbols:
        candle_cache[symbol] = backtest.fetch_history(symbol)

    configs = [("ALL COMPONENTS (current live behaviour)", {})]

    for component in COMPONENTS:
        configs.append((f"WITHOUT {component}", {component: False}))

    rows = []

    for label, kwargs in configs:

        trades = backtest.run_backtest(
            symbols=all_symbols,
            candle_cache=candle_cache,
            verbose=False,
            **kwargs,
        )

        train_trades, test_trades = optimize.split_trades(trades, split_ts)

        train_stats = optimize.summarise(train_trades)
        test_stats = optimize.summarise(test_trades)

        rows.append([
            label,
            train_stats["count"],
            f"{train_stats['win_rate']:.1f}%",
            f"{train_stats['expectancy']:+.3f}%",
            test_stats["count"],
            f"{test_stats['win_rate']:.1f}%",
            f"{test_stats['expectancy']:+.3f}%",
        ])

    print()
    print("=" * 100)
    print("SIGNAL COMPONENT ABLATION")
    print("=" * 100)
    print(tabulate(
        rows,
        headers=[
            "Config",
            "Train N", "Train WR", "Train Exp",
            "Test N", "Test WR", "Test Exp",
        ],
    ))
    print()
    print(
        "Compare each row's Test Exp against the baseline row's. A "
        "component whose removal IMPROVES test expectancy is a "
        "candidate to drop or reweight -- but only trust it if the "
        "test N is large enough to mean something (see the ATR=20 "
        "rejection in OPTIMIZATION_LOG.md for what happens when it isn't)."
    )
    print("=" * 100)


if __name__ == "__main__":
    run_ablation()
