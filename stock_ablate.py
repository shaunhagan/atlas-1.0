"""
=========================================
ATLAS AI
Stock Signal Component Ablation
=========================================

The exit-parameter sweep (stock_optimize.py) rejected -- same
overfitting trap as crypto's ATR=20 (STOCK_OPTIMIZATION_LOG.md,
2026-08-27). This tests the other half: does each individual scoring
component in signals.py actually contribute positive out-of-sample
expectancy on stocks specifically, or is one of them dead weight (or
actively harmful) the way momentum was for crypto?

Same train/test discipline throughout, split anchored to the cached
data's own span (not live time -- see optimize.compute_split_ts).
"""

from tabulate import tabulate

import stock_backtest
import optimize


ABLATION_SYMBOL_LIMIT = stock_backtest.SYMBOL_LIMIT

ABLATION_DAYS = 90

COMPONENTS = [
    "use_trend",
    "use_rsi",
    "use_macd",
    "use_momentum",
    "use_volume",
    "use_chop_gate",
]


def run_ablation(symbol_limit=ABLATION_SYMBOL_LIMIT):

    all_symbols = stock_backtest.exchange.get_markets()[:symbol_limit]

    print(f"Loading cached history for {len(all_symbols)} symbols ({ABLATION_DAYS} days)...")

    candle_cache = {}

    for symbol in all_symbols:
        candle_cache[symbol] = stock_backtest.fetch_history(symbol, days=ABLATION_DAYS)

    split_ts = optimize.compute_split_ts(candle_cache)

    configs = [("ALL COMPONENTS (current live behaviour)", {})]

    for component in COMPONENTS:
        configs.append((f"WITHOUT {component}", {component: False}))

    rows = []

    for label, kwargs in configs:

        trades = stock_backtest.run_backtest(
            symbols=all_symbols,
            days=ABLATION_DAYS,
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
    print("STOCK SIGNAL COMPONENT ABLATION")
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
        "candidate to drop -- but only trust it if the test N is "
        "large enough to mean something (see the ATR=20/stock sweep "
        "rejections for what happens when it isn't)."
    )
    print("=" * 100)


if __name__ == "__main__":
    run_ablation()
