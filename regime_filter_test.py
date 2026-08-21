"""
=========================================
ATLAS AI
Market Regime Filter Test
=========================================

OPTIMIZATION_LOG.md (2026-08-20/21): the strategy shows positive
expectancy only in the calm/flat window (BTC volatility ~0.080%,
change +0.21%) and negative expectancy in both higher-volatility,
declining windows (~0.128%/0.146% volatility, -2.42%/-14.67% change).

This tests one specific, pre-chosen hypothesis -- gate new entries on
BTC's own trailing volatility being below a threshold -- against all
three known windows. The threshold (0.10%, roughly the midpoint
between the calm and elevated aggregate levels already observed) is
chosen ONCE, up front, not fit per-window. Fitting a threshold
separately to each window's known outcome would be the same
overfitting trap as the rejected ATR=20 sweep result.
"""

import pandas as pd
from tabulate import tabulate

import backtest


REGIME_SYMBOL_LIMIT = 40

REGIME_LOOKBACK = 200

VOLATILITY_THRESHOLD_PCT = 0.10

WINDOWS = [
    ("Primary (last 30d)", 0),
    ("Second (35-65d ago)", 35),
    ("Third (65-95d ago)", 65),
]


def build_regime_filter(btc_candles, threshold_pct, period=REGIME_LOOKBACK):

    df = pd.DataFrame(
        btc_candles,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )

    returns = df["close"].pct_change()

    rolling_vol_pct = returns.rolling(period).std() * 100

    vol_by_ts = dict(zip(df["timestamp"], rolling_vol_pct))

    def regime_ok(ts):

        vol = vol_by_ts.get(ts)

        if vol is None or pd.isna(vol):
            return True

        return vol < threshold_pct

    return regime_ok


def run():

    symbols = backtest.exchange.get_markets()[:REGIME_SYMBOL_LIMIT]

    rows = []

    for label, end_days_ago in WINDOWS:

        print(f"\n--- {label} ---")

        cache = {}

        for symbol in symbols:
            cache[symbol] = backtest.fetch_history(
                symbol, days=30, end_days_ago=end_days_ago,
            )

        btc_candles = cache.get("BTC/USDT") or backtest.fetch_history(
            "BTC/USDT", days=30, end_days_ago=end_days_ago,
        )

        regime_ok = build_regime_filter(btc_candles, VOLATILITY_THRESHOLD_PCT)

        baseline_trades = backtest.run_backtest(
            symbols=symbols, candle_cache=cache, verbose=False,
        )

        filtered_trades = backtest.run_backtest(
            symbols=symbols, candle_cache=cache, verbose=False,
            regime_ok_fn=regime_ok,
        )

        for tag, trades in [("No filter", baseline_trades), ("With regime filter", filtered_trades)]:

            wins = [t for t in trades if t["pnl_pct"] > 0]
            win_rate = len(wins) / len(trades) * 100 if trades else 0.0
            expectancy = sum(t["pnl_pct"] for t in trades) / len(trades) if trades else 0.0

            rows.append([label, tag, len(trades), f"{win_rate:.1f}%", f"{expectancy:+.3f}%"])

    print("\n" + "=" * 80)
    print(f"REGIME FILTER TEST (BTC trailing {REGIME_LOOKBACK}-candle volatility < {VOLATILITY_THRESHOLD_PCT}%)")
    print("=" * 80)
    print(tabulate(rows, headers=["Window", "Config", "Trades", "Win Rate", "Expectancy"]))
    print("=" * 80)


if __name__ == "__main__":
    run()
