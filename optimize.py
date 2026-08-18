"""
=========================================
ATLAS AI
Parameter Sweep
=========================================

Uses backtest.py to search for a better-than-baseline
configuration. Staged (coordinate-descent) rather than full grid
search to stay fast: sweep ATR_STOP_MULTIPLIER first, lock in the
best, sweep RISK_REWARD_RATIO next, lock that in, then sweep
MIN_CONFIDENCE. Not guaranteed globally optimal, but fast and a
large improvement over hand-guessing.

Overfitting guard: every sweep decision is made using only trades
from the TRAIN period (the earlier ~75% of the fetched history).
The last ~25% is held out entirely from tuning. The final winning
config is confirmed against the current live baseline on both the
full symbol set and, critically, on the held-out test period alone
-- if the "winner" doesn't hold up there, it was overfit to the
train period and shouldn't be trusted.
"""

from tabulate import tabulate

import backtest
from config import (
    ATR_STOP_MULTIPLIER,
    RISK_REWARD_RATIO,
    MIN_CONFIDENCE,
)


SWEEP_SYMBOL_LIMIT = 30

MIN_TRADES_FOR_SIGNIFICANCE = 20

TEST_FRACTION = 0.25

ATR_STOP_MULTIPLIER_GRID = [5, 8, 10, 14, 20]

RISK_REWARD_RATIO_GRID = [1.5, 2.0, 2.5, 3.0, 4.0]

MIN_CONFIDENCE_GRID = [55, 60, 65, 70, 75, 80]


def summarise(trades):

    if not trades:
        return {"count": 0, "win_rate": 0.0, "expectancy": 0.0}

    wins = [t for t in trades if t["pnl_pct"] > 0]

    return {
        "count": len(trades),
        "win_rate": len(wins) / len(trades) * 100,
        "expectancy": sum(t["pnl_pct"] for t in trades) / len(trades),
    }


def split_trades(trades, split_ts):
    """Trades entered before split_ts are TRAIN, on/after are TEST."""

    train = [t for t in trades if t["entry_ts"] < split_ts]
    test = [t for t in trades if t["entry_ts"] >= split_ts]

    return train, test


def sweep(label, param_name, grid, candle_cache, symbols, fixed_kwargs, split_ts):
    """Every decision here uses TRAIN trades only -- the held-out
    test period is never touched until the final confirmation."""

    print(f"\n--- Sweeping {label} (train period only) ---")

    rows = []
    results = []

    for value in grid:

        kwargs = dict(fixed_kwargs)
        kwargs[param_name] = value

        trades = backtest.run_backtest(
            symbols=symbols,
            candle_cache=candle_cache,
            verbose=False,
            **kwargs,
        )

        train_trades, _ = split_trades(trades, split_ts)

        stats = summarise(train_trades)
        results.append((value, stats))

        rows.append([
            value,
            stats["count"],
            f"{stats['win_rate']:.1f}%",
            f"{stats['expectancy']:+.3f}%",
        ])

    print(tabulate(
        rows,
        headers=[label, "Train Trades", "Win Rate", "Expectancy/Trade"],
    ))

    significant = [
        (value, stats) for value, stats in results
        if stats["count"] >= MIN_TRADES_FOR_SIGNIFICANCE
    ]

    pool = significant if significant else results

    best_value, best_stats = max(pool, key=lambda item: item[1]["expectancy"])

    print(f"Best {label}: {best_value} (train expectancy {best_stats['expectancy']:+.3f}%, {best_stats['count']} trades)")

    return best_value


def run_optimization():

    all_symbols = backtest.exchange.get_markets()[:backtest.SYMBOL_LIMIT]
    sweep_symbols = all_symbols[:SWEEP_SYMBOL_LIMIT]

    split_ts = backtest.exchange.now_ms() - int(
        backtest.BACKTEST_DAYS * TEST_FRACTION * 24 * 60 * 60 * 1000
    )

    print(f"Loading cached history for {len(sweep_symbols)} sweep symbols...")
    print(f"Train/test split: last {TEST_FRACTION*100:.0f}% of the {backtest.BACKTEST_DAYS}-day window held out.\n")

    candle_cache = {}

    for symbol in sweep_symbols:
        candle_cache[symbol] = backtest.fetch_history(symbol)

    fixed = {
        "atr_stop_multiplier": ATR_STOP_MULTIPLIER,
        "risk_reward_ratio": RISK_REWARD_RATIO,
        "min_confidence": MIN_CONFIDENCE,
    }

    best_atr = sweep(
        "ATR_STOP_MULTIPLIER", "atr_stop_multiplier",
        ATR_STOP_MULTIPLIER_GRID, candle_cache, sweep_symbols, fixed, split_ts,
    )
    fixed["atr_stop_multiplier"] = best_atr

    best_rr = sweep(
        "RISK_REWARD_RATIO", "risk_reward_ratio",
        RISK_REWARD_RATIO_GRID, candle_cache, sweep_symbols, fixed, split_ts,
    )
    fixed["risk_reward_ratio"] = best_rr

    best_conf = sweep(
        "MIN_CONFIDENCE", "min_confidence",
        MIN_CONFIDENCE_GRID, candle_cache, sweep_symbols, fixed, split_ts,
    )
    fixed["min_confidence"] = best_conf

    print("\n" + "=" * 70)
    print("WINNING CONFIG (from train-period sweep):")
    print(f"  ATR_STOP_MULTIPLIER = {best_atr}")
    print(f"  RISK_REWARD_RATIO   = {best_rr}")
    print(f"  MIN_CONFIDENCE      = {best_conf}")
    print("=" * 70)

    # ----------------------------------------------------------
    # Confirm on the FULL cached symbol universe -- baseline vs
    # winner, on both the full period and the held-out test period
    # specifically. This is the real answer: does the winner's
    # edge survive on data it never saw during tuning?
    # ----------------------------------------------------------

    print(f"\nLoading full {len(all_symbols)}-symbol cache for confirmation run...")

    full_cache = dict(candle_cache)

    for symbol in all_symbols:
        if symbol not in full_cache:
            full_cache[symbol] = backtest.fetch_history(symbol)

    baseline_trades = backtest.run_backtest(
        symbols=all_symbols, candle_cache=full_cache, verbose=False,
    )

    winner_trades = backtest.run_backtest(
        symbols=all_symbols, candle_cache=full_cache, verbose=False,
        atr_stop_multiplier=best_atr,
        risk_reward_ratio=best_rr,
        min_confidence=best_conf,
    )

    baseline_train, baseline_test = split_trades(baseline_trades, split_ts)
    winner_train, winner_test = split_trades(winner_trades, split_ts)

    def row(label, trades):
        stats = summarise(trades)
        return [label, stats["count"], f"{stats['win_rate']:.1f}%", f"{stats['expectancy']:+.3f}%"]

    print("\n" + "=" * 70)
    print("CONFIRMATION -- baseline (live config) vs winning config")
    print("=" * 70)
    print(tabulate(
        [
            row("Baseline - full period", baseline_trades),
            row("Baseline - TEST period (held out)", baseline_test),
            row("Winner - full period", winner_trades),
            row("Winner - TEST period (held out)", winner_test),
        ],
        headers=["Config", "Trades", "Win Rate", "Expectancy/Trade"],
    ))
    print("=" * 70)
    print(
        "\nTrust the TEST-period rows over the full-period rows -- "
        "that's the data neither config was tuned on."
    )


if __name__ == "__main__":
    run_optimization()
