"""
=========================================
ATLAS AI
Stock Mean-Reversion -- SPY Trend-Direction Gate Test
=========================================

ADX (trend strength, direction-agnostic) and SPY realised volatility
both failed to reconcile window 1 (train -0.482%) vs window 2 (train
+1.601%) -- see STOCK_OPTIMIZATION_LOG.md 2026-08-29, both rejected.

Checked SPY's overall move in each window directly: window 1 +1.65%
(90 days), window 2 +11.38% -- both net positive, so it isn't a
decline vs rally story either. But window 2 was a much stronger,
more sustained uptrend than window 1's comparatively flat/choppy
gain. This tests a narrower hypothesis: does gating entries on SPY
being in a clear uptrend (price > its own medium-term EMA, no
volatility condition attached, unlike the already-rejected combined
filter) help -- i.e. does mean-reversion here need the dip to be
happening inside a real uptrend to be safely bought, rather than
"low volatility" being the relevant condition?
"""

import pandas as pd
from tabulate import tabulate

import stock_backtest
import stock_meanrev_backtest
import optimize
from config import EMA_SLOW


WINDOWS = [
    ("Window 1 (last 90d)", 0),
    ("Window 2 (90-180d ago)", 90),
]


def build_trend_only_filter(spy_candles):

    df = pd.DataFrame(
        spy_candles,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )

    ema_slow = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()

    price_by_ts = dict(zip(df["timestamp"], df["close"]))
    ema_by_ts = dict(zip(df["timestamp"], ema_slow))

    def trend_ok(ts):

        price = price_by_ts.get(ts)
        ema = ema_by_ts.get(ts)

        if price is None or ema is None or pd.isna(ema):
            return True

        return price > ema

    return trend_ok


def main():

    symbols = stock_backtest.exchange.get_markets()[:stock_backtest.SYMBOL_LIMIT]

    rows = []

    for window_label, end_days_ago in WINDOWS:

        print(f"\n--- {window_label} ---")

        candle_cache = {}

        for symbol in symbols:
            candle_cache[symbol] = stock_backtest.fetch_history(
                symbol, days=90, end_days_ago=end_days_ago,
            )

        spy_candles = candle_cache.get("SPY") or stock_backtest.fetch_history(
            "SPY", days=90, end_days_ago=end_days_ago,
        )

        trend_ok = build_trend_only_filter(spy_candles)

        split_ts = optimize.compute_split_ts(candle_cache)

        for label, regime_fn in [("No filter", None), ("SPY uptrend only", trend_ok)]:

            trades = stock_meanrev_backtest.run_backtest(
                symbols=symbols, days=90, candle_cache=candle_cache,
                verbose=False, regime_ok_fn=regime_fn,
            )

            train, test = optimize.split_trades(trades, split_ts)

            train_stats = optimize.summarise(train)
            test_stats = optimize.summarise(test)

            rows.append([
                window_label, label,
                train_stats["count"], f"{train_stats['expectancy']:+.3f}%",
                test_stats["count"], f"{test_stats['expectancy']:+.3f}%",
            ])

    print("\n" + "=" * 100)
    print("STOCK MEAN-REVERSION -- SPY TREND-DIRECTION GATE, BOTH WINDOWS")
    print("=" * 100)
    print(tabulate(
        rows,
        headers=["Window", "Gate", "Train N", "Train Exp", "Test N", "Test Exp"],
    ))
    print("=" * 100)


if __name__ == "__main__":
    main()
