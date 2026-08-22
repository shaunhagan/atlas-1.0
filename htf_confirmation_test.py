"""
=========================================
ATLAS AI
Multi-Timeframe Confirmation Test
=========================================

Tests requiring 1h trend agreement (per-symbol EMA_FAST > EMA_SLOW on
the 1h timeframe, resampled from already-cached 5m data, no extra
fetch) before allowing a 5m BUY entry. Also tests it stacked on top
of the already-live volatility regime filter, since that's the
config that would actually go live if this helps.
"""

from tabulate import tabulate

import backtest
import regime_filter_test as regime_test


CONFIRMATION_SYMBOL_LIMIT = 40

WINDOWS = [
    ("Primary (last 30d)", 0),
    ("Second (35-65d ago)", 35),
    ("Third (65-95d ago)", 65),
]


def run():

    symbols = backtest.exchange.get_markets()[:CONFIRMATION_SYMBOL_LIMIT]

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

        volatility_only, _ = regime_test.build_regime_filters(
            btc_candles, regime_test.VOLATILITY_THRESHOLD_PCT,
        )

        configs = [
            ("No filter", {}),
            ("1h confirmation only", {"require_htf_confirmation": True}),
            ("Volatility filter (live)", {"regime_ok_fn": volatility_only}),
            (
                "Volatility + 1h confirmation",
                {"regime_ok_fn": volatility_only, "require_htf_confirmation": True},
            ),
        ]

        for tag, kwargs in configs:

            trades = backtest.run_backtest(
                symbols=symbols, candle_cache=cache, verbose=False, **kwargs,
            )

            wins = [t for t in trades if t["pnl_pct"] > 0]
            win_rate = len(wins) / len(trades) * 100 if trades else 0.0
            expectancy = sum(t["pnl_pct"] for t in trades) / len(trades) if trades else 0.0

            rows.append([label, tag, len(trades), f"{win_rate:.1f}%", f"{expectancy:+.3f}%"])

    print("\n" + "=" * 90)
    print("MULTI-TIMEFRAME CONFIRMATION TEST (per-symbol 1h EMA20 > EMA50)")
    print("=" * 90)
    print(tabulate(rows, headers=["Window", "Config", "Trades", "Win Rate", "Expectancy"]))
    print("=" * 90)


if __name__ == "__main__":
    run()
