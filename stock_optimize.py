"""
=========================================
ATLAS AI
Stock Parameter Sweep
=========================================

Mirrors optimize.py's approach exactly (staged coordinate-descent
sweep, train/test discipline throughout), pointed at stock_backtest.py
and the STOCK_* config. Reuses optimize.py's summarise/split_trades/
compute_split_ts directly since they're generic over any
candle_cache/trades shape, not crypto-specific.

Uses a 90-day window, not 30 -- STOCK_OPTIMIZATION_LOG.md 2026-08-26/27
found 30 days doesn't give enough trades for a trustworthy held-out
test bucket on stocks (far fewer trading hours/week than crypto).
"""

from tabulate import tabulate

import stock_backtest
import optimize
from config import (
    STOCK_ATR_STOP_MULTIPLIER,
    STOCK_RISK_REWARD_RATIO,
    MIN_CONFIDENCE,
)


SWEEP_SYMBOL_LIMIT = stock_backtest.SYMBOL_LIMIT

SWEEP_DAYS = 90

MIN_TRADES_FOR_SIGNIFICANCE = 20

ATR_STOP_MULTIPLIER_GRID = [5, 8, 10, 14, 20]

RISK_REWARD_RATIO_GRID = [1.5, 2.0, 2.5, 3.0, 4.0]

MIN_CONFIDENCE_GRID = [55, 60, 65, 70, 75, 80]


def sweep(label, param_name, grid, candle_cache, symbols, fixed_kwargs, split_ts):
    """Every decision here uses TRAIN trades only -- the held-out
    test period is never touched until the final confirmation."""

    print(f"\n--- Sweeping {label} (train period only) ---")

    rows = []
    results = []

    for value in grid:

        kwargs = dict(fixed_kwargs)
        kwargs[param_name] = value

        trades = stock_backtest.run_backtest(
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

    all_symbols = stock_backtest.exchange.get_markets()[:SWEEP_SYMBOL_LIMIT]

    print(f"Loading cached history for {len(all_symbols)} symbols ({SWEEP_DAYS} days)...")
    print(f"Train/test split: last 25% of the {SWEEP_DAYS}-day window held out.\n")

    candle_cache = {}

    for symbol in all_symbols:
        candle_cache[symbol] = stock_backtest.fetch_history(symbol, days=SWEEP_DAYS)

    split_ts = optimize.compute_split_ts(candle_cache)

    fixed = {
        "atr_stop_multiplier": STOCK_ATR_STOP_MULTIPLIER,
        "risk_reward_ratio": STOCK_RISK_REWARD_RATIO,
        "min_confidence": MIN_CONFIDENCE,
    }

    best_atr = sweep(
        "ATR_STOP_MULTIPLIER", "atr_stop_multiplier",
        ATR_STOP_MULTIPLIER_GRID, candle_cache, all_symbols, fixed, split_ts,
    )
    fixed["atr_stop_multiplier"] = best_atr

    best_rr = sweep(
        "RISK_REWARD_RATIO", "risk_reward_ratio",
        RISK_REWARD_RATIO_GRID, candle_cache, all_symbols, fixed, split_ts,
    )
    fixed["risk_reward_ratio"] = best_rr

    best_conf = sweep(
        "MIN_CONFIDENCE", "min_confidence",
        MIN_CONFIDENCE_GRID, candle_cache, all_symbols, fixed, split_ts,
    )
    fixed["min_confidence"] = best_conf

    print("\n" + "=" * 70)
    print("WINNING CONFIG (from train-period sweep):")
    print(f"  STOCK_ATR_STOP_MULTIPLIER = {best_atr}")
    print(f"  STOCK_RISK_REWARD_RATIO   = {best_rr}")
    print(f"  MIN_CONFIDENCE            = {best_conf}")
    print("=" * 70)

    # ----------------------------------------------------------
    # Confirm baseline vs winner, on both the full period and the
    # held-out test period specifically -- same universe (already
    # fully cached, no separate "sweep subset vs full universe" step
    # needed since the stock universe is only 50 symbols).
    # ----------------------------------------------------------

    baseline_trades = stock_backtest.run_backtest(
        symbols=all_symbols, days=SWEEP_DAYS, candle_cache=candle_cache, verbose=False,
    )

    winner_trades = stock_backtest.run_backtest(
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
    print("CONFIRMATION -- baseline (crypto-transplanted config) vs winning config")
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
