"""
=========================================
ATLAS AI
Meme Coin Parameter Sweep
=========================================

Mirrors optimize.py/stock_optimize.py's staged coordinate-descent
sweep, pointed at meme_backtest.py and the MEME_* config. Reuses
optimize.py's summarise/split_trades/compute_split_ts directly since
they're generic over any candle_cache/trades shape.

Uses a 30-day window -- MEME_OPTIMIZATION_LOG.md 2026-08-27 already
confirmed this yields 275 train / 101 test trades, comfortably above
MIN_TRADES_FOR_SIGNIFICANCE, via the Binance-sourced hybrid fetch in
meme_backtest.fetch_history (Kraken alone can't reach 30 days).
"""

from tabulate import tabulate

import meme_backtest
import optimize
from config import (
    MEME_ATR_STOP_MULTIPLIER,
    MEME_RISK_REWARD_RATIO,
    MEME_MIN_CONFIDENCE,
    MEME_SCAN_LIMIT,
)


SWEEP_SYMBOL_LIMIT = MEME_SCAN_LIMIT

SWEEP_DAYS = 30

MIN_TRADES_FOR_SIGNIFICANCE = 20

ATR_STOP_MULTIPLIER_GRID = [3, 4, 6, 8, 10]

RISK_REWARD_RATIO_GRID = [2.0, 2.5, 3.0, 3.5, 4.5]

MIN_CONFIDENCE_GRID = [50, 55, 60, 65, 70]


def sweep(label, param_name, grid, candle_cache, symbols, fixed_kwargs, split_ts):
    """Every decision here uses TRAIN trades only -- the held-out
    test period is never touched until the final confirmation."""

    print(f"\n--- Sweeping {label} (train period only) ---")

    rows = []
    results = []

    for value in grid:

        kwargs = dict(fixed_kwargs)
        kwargs[param_name] = value

        trades = meme_backtest.run_backtest(
            symbols=symbols,
            days=SWEEP_DAYS,
            candle_cache=candle_cache,
            verbose=False,
            **kwargs,
        )

        train_trades, _ = optimize.split_trades(trades, split_ts)

        stats = optimize.summarise(train_trades)
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

    all_symbols = meme_backtest.exchange.get_markets()[:SWEEP_SYMBOL_LIMIT]

    print(f"Loading cached history for {len(all_symbols)} symbols ({SWEEP_DAYS} days)...")
    print(f"Train/test split: last 25% of the {SWEEP_DAYS}-day window held out.\n")

    candle_cache = {}

    for symbol in all_symbols:
        candle_cache[symbol] = meme_backtest.fetch_history(symbol, days=SWEEP_DAYS)

    split_ts = optimize.compute_split_ts(candle_cache)

    fixed = {
        "atr_stop_multiplier": MEME_ATR_STOP_MULTIPLIER,
        "risk_reward_ratio": MEME_RISK_REWARD_RATIO,
        "min_confidence": MEME_MIN_CONFIDENCE,
    }

    best_atr = sweep(
        "MEME_ATR_STOP_MULTIPLIER", "atr_stop_multiplier",
        ATR_STOP_MULTIPLIER_GRID, candle_cache, all_symbols, fixed, split_ts,
    )
    fixed["atr_stop_multiplier"] = best_atr

    best_rr = sweep(
        "MEME_RISK_REWARD_RATIO", "risk_reward_ratio",
        RISK_REWARD_RATIO_GRID, candle_cache, all_symbols, fixed, split_ts,
    )
    fixed["risk_reward_ratio"] = best_rr

    best_conf = sweep(
        "MEME_MIN_CONFIDENCE", "min_confidence",
        MIN_CONFIDENCE_GRID, candle_cache, all_symbols, fixed, split_ts,
    )
    fixed["min_confidence"] = best_conf

    print("\n" + "=" * 70)
    print("WINNING CONFIG (from train-period sweep):")
    print(f"  MEME_ATR_STOP_MULTIPLIER = {best_atr}")
    print(f"  MEME_RISK_REWARD_RATIO   = {best_rr}")
    print(f"  MEME_MIN_CONFIDENCE      = {best_conf}")
    print("=" * 70)

    # ----------------------------------------------------------
    # Confirm baseline (current live settings) vs winner, on both
    # the full period and the held-out test period specifically.
    # ----------------------------------------------------------

    baseline_trades = meme_backtest.run_backtest(
        symbols=all_symbols, days=SWEEP_DAYS, candle_cache=candle_cache, verbose=False,
    )

    winner_trades = meme_backtest.run_backtest(
        symbols=all_symbols, days=SWEEP_DAYS, candle_cache=candle_cache, verbose=False,
        atr_stop_multiplier=best_atr,
        risk_reward_ratio=best_rr,
        min_confidence=best_conf,
    )

    baseline_train, baseline_test = optimize.split_trades(baseline_trades, split_ts)
    winner_train, winner_test = optimize.split_trades(winner_trades, split_ts)

    def row(label, trades):
        stats = optimize.summarise(trades)
        return [label, stats["count"], f"{stats['win_rate']:.1f}%", f"{stats['expectancy']:+.3f}%"]

    print("\n" + "=" * 70)
    print("CONFIRMATION -- baseline (current live config) vs winning config")
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
