"""
=========================================
ATLAS AI
Stock Portfolio Heat Gate -- Validation
=========================================

Same idea as meme_portfolio_heat_test.py, applied to the mean-reversion
strategy now live for stocks: does pausing new entries when most of
the currently open book is underwater help, tested with the
shared-state portfolio_backtest.py engine (the per-symbol independent
stock_meanrev_backtest.py can't test this -- no concept of concurrent
positions across symbols).
"""

from tabulate import tabulate

import stock_backtest
import portfolio_backtest
import optimize
from indicators import Indicators
from config import (
    STOCK_MAX_OPEN_TRADES,
    STOCK_ATR_STOP_MULTIPLIER,
    STOCK_RISK_REWARD_RATIO,
    STOCK_TRADING_FRICTION_PCT,
    STOCK_CANDLE_LIMIT,
    BOLLINGER_PERIOD,
    BOLLINGER_STDDEV,
    MEANREV_RSI_OVERSOLD,
)


TEST_DAYS = 90


def meanrev_signal_fn(closes, highs, lows, volumes):

    rsi = Indicators.rsi(closes)
    upper, middle, lower = Indicators.bollinger_bands(
        closes, BOLLINGER_PERIOD, BOLLINGER_STDDEV,
    )

    price = closes[-1]

    if rsi != rsi or lower != lower:
        return "HOLD", 0

    if price <= lower and rsi < MEANREV_RSI_OVERSOLD:
        return "BUY", 75

    return "HOLD", 0


def main():

    symbols = stock_backtest.exchange.get_markets()[:stock_backtest.SYMBOL_LIMIT]

    print(f"Loading cached history for {len(symbols)} symbols ({TEST_DAYS} days)...")

    candle_cache = {
        s: stock_backtest.fetch_history(s, days=TEST_DAYS) for s in symbols
    }

    split_ts = optimize.compute_split_ts(candle_cache)

    lookback = max(STOCK_CANDLE_LIMIT, BOLLINGER_PERIOD)

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
            signal_fn=meanrev_signal_fn,
            lookback=lookback,
            max_open_trades=STOCK_MAX_OPEN_TRADES,
            atr_stop_multiplier=STOCK_ATR_STOP_MULTIPLIER,
            risk_reward_ratio=STOCK_RISK_REWARD_RATIO,
            friction_pct=STOCK_TRADING_FRICTION_PCT,
            use_heat_gate=use_gate,
            verbose=True,
        )

        train, test = optimize.split_trades(trades, split_ts)

        train_stats = optimize.summarise(train)
        test_stats = optimize.summarise(test)

        rows.append([
            label,
            train_stats["count"], f"{train_stats['win_rate']:.1f}%", f"{train_stats['expectancy']:+.3f}%",
            test_stats["count"], f"{test_stats['win_rate']:.1f}%", f"{test_stats['expectancy']:+.3f}%",
        ])

    print("\n" + "=" * 110)
    print("STOCK PORTFOLIO HEAT GATE -- TRAIN/TEST (shared-state portfolio backtest)")
    print("=" * 110)
    print(tabulate(
        rows,
        headers=["Config", "Train N", "Train WR", "Train Exp", "Test N", "Test WR", "Test Exp"],
    ))
    print("=" * 110)


if __name__ == "__main__":
    main()
