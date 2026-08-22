"""
=========================================
ATLAS AI
Market Regime Filter Test
=========================================

OPTIMIZATION_LOG.md (2026-08-20/21): the strategy shows positive
expectancy only in the calm/flat window (BTC volatility ~0.080%,
change +0.21%) and negative expectancy in both higher-volatility,
declining windows (~0.128%/0.146% volatility, -2.42%/-14.67% change).
A volatility-only gate (<0.10%) helped but didn't fully fix either
losing window.

This tests a second, still-pre-chosen hypothesis: combine the
volatility gate with BTC's own trend (price > EMA50, same EMA_SLOW
period the signal engine itself uses) -- both conditions chosen once,
up front, not fit per-window, for the same overfitting-avoidance
reason as before.
"""

import pandas as pd
from tabulate import tabulate

import backtest
from config import EMA_SLOW


REGIME_SYMBOL_LIMIT = 40

REGIME_LOOKBACK = 200

VOLATILITY_THRESHOLD_PCT = 0.10

WINDOWS = [
    ("Primary (last 30d)", 0),
    ("Second (35-65d ago)", 35),
    ("Third (65-95d ago)", 65),
]


def build_regime_filters(btc_candles, threshold_pct, period=REGIME_LOOKBACK):

    df = pd.DataFrame(
        btc_candles,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )

    returns = df["close"].pct_change()

    rolling_vol_pct = returns.rolling(period).std() * 100

    rolling_ema_slow = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()

    vol_by_ts = dict(zip(df["timestamp"], rolling_vol_pct))
    price_by_ts = dict(zip(df["timestamp"], df["close"]))
    ema_by_ts = dict(zip(df["timestamp"], rolling_ema_slow))

    def volatility_only(ts):

        vol = vol_by_ts.get(ts)

        if vol is None or pd.isna(vol):
            return True

        return vol < threshold_pct

    def volatility_and_trend(ts):

        vol = vol_by_ts.get(ts)
        price = price_by_ts.get(ts)
        ema = ema_by_ts.get(ts)

        if vol is None or pd.isna(vol) or price is None or ema is None or pd.isna(ema):
            return True

        return (vol < threshold_pct) and (price > ema)

    return volatility_only, volatility_and_trend


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

        volatility_only, volatility_and_trend = build_regime_filters(
            btc_candles, VOLATILITY_THRESHOLD_PCT,
        )

        configs = [
            ("No filter", None),
            ("Volatility only", volatility_only),
            ("Volatility + trend", volatility_and_trend),
        ]

        for tag, regime_fn in configs:

            trades = backtest.run_backtest(
                symbols=symbols, candle_cache=cache, verbose=False,
                regime_ok_fn=regime_fn,
            )

            wins = [t for t in trades if t["pnl_pct"] > 0]
            win_rate = len(wins) / len(trades) * 100 if trades else 0.0
            expectancy = sum(t["pnl_pct"] for t in trades) / len(trades) if trades else 0.0

            rows.append([label, tag, len(trades), f"{win_rate:.1f}%", f"{expectancy:+.3f}%"])

    print("\n" + "=" * 80)
    print(f"REGIME FILTER TEST v2 (volatility < {VOLATILITY_THRESHOLD_PCT}%, trend = BTC price > EMA{EMA_SLOW})")
    print("=" * 80)
    print(tabulate(rows, headers=["Window", "Config", "Trades", "Win Rate", "Expectancy"]))
    print("=" * 80)


if __name__ == "__main__":
    run()
