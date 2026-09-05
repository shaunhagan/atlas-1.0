"""
=========================================
ATLAS AI
Meme Coin Portfolio Heat Gate -- Validation
=========================================

Tests whether a book-wide "heat" gate (pause new entries when most of
the currently open positions are already underwater) helps, using the
new shared-state portfolio_backtest.py engine -- the per-symbol
independent backtesters can't test this at all, since they have no
concept of concurrently open positions across symbols.

Directly motivated by the 2026-08-28/30 live drawdown: 16 of 18
traded meme coins were net negative at once, a correlated/systemic
move a position-COUNT cap (MEME_MAX_OPEN_TRADES) gives no protection
against.
"""

from tabulate import tabulate

import meme_backtest
import portfolio_backtest
import optimize
from indicators import Indicators
from signals import SignalEngine
from config import (
    MEME_SCAN_LIMIT,
    MEME_MAX_OPEN_TRADES,
    MEME_ATR_STOP_MULTIPLIER,
    MEME_RISK_REWARD_RATIO,
    MEME_TRADING_FRICTION_PCT,
    MEME_MIN_CONFIDENCE,
    CANDLE_LIMIT,
)


TEST_DAYS = 30


def meme_signal_fn(closes, highs, lows, volumes):

    ema_fast = Indicators.ema_fast(closes)
    ema_slow = Indicators.ema_slow(closes)
    rsi = Indicators.rsi(closes)
    macd, signal, histogram = Indicators.macd(closes)
    volume_ratio = Indicators.volume_ratio(volumes)

    result = SignalEngine.evaluate(
        closes[-1], ema_fast, ema_slow, rsi, macd, signal, histogram,
        volume_ratio, min_confidence=MEME_MIN_CONFIDENCE,
    )

    return result["decision"], result["confidence"]


def main():

    symbols = meme_backtest.exchange.get_markets()[:MEME_SCAN_LIMIT]

    print(f"Loading cached history for {len(symbols)} symbols ({TEST_DAYS} days)...")

    candle_cache = {s: meme_backtest.fetch_history(s, days=TEST_DAYS) for s in symbols}

    split_ts = optimize.compute_split_ts(candle_cache)

    configs = [
        ("No heat gate (current live)", False),
        ("Heat gate (60% underwater, min 4 open)", True),
    ]

    rows = []

    for label, use_gate in configs:

        print(f"\n--- {label} ---")

        trades, heat_history = portfolio_backtest.run_portfolio_backtest(
            symbols=symbols,
            candle_cache=candle_cache,
            signal_fn=meme_signal_fn,
            lookback=CANDLE_LIMIT,
            max_open_trades=MEME_MAX_OPEN_TRADES,
            atr_stop_multiplier=MEME_ATR_STOP_MULTIPLIER,
            risk_reward_ratio=MEME_RISK_REWARD_RATIO,
            friction_pct=MEME_TRADING_FRICTION_PCT,
            use_heat_gate=use_gate,
            verbose=True,
        )

        train, test = optimize.split_trades(trades, split_ts)

        train_stats = optimize.summarise(train)
        test_stats = optimize.summarise(test)

        max_drawdown_positions = max(
            (n for _, n, _ in heat_history), default=0,
        )

        rows.append([
            label,
            train_stats["count"], f"{train_stats['win_rate']:.1f}%", f"{train_stats['expectancy']:+.3f}%",
            test_stats["count"], f"{test_stats['win_rate']:.1f}%", f"{test_stats['expectancy']:+.3f}%",
        ])

    print("\n" + "=" * 110)
    print("MEME COIN PORTFOLIO HEAT GATE -- TRAIN/TEST (shared-state portfolio backtest)")
    print("=" * 110)
    print(tabulate(
        rows,
        headers=["Config", "Train N", "Train WR", "Train Exp", "Test N", "Test WR", "Test Exp"],
    ))
    print("=" * 110)


if __name__ == "__main__":
    main()
