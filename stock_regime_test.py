"""
=========================================
ATLAS AI
Stock Regime Filter Test
=========================================

The volatility regime filter is validated and LIVE for crypto (BTC
realised volatility as a market-wide risk proxy, OPTIMIZATION_LOG.md
2026-08-23) but was deliberately NOT carried over to the stock tier at
launch -- STOCK_OPTIMIZATION_LOG.md notes it was "validated specifically
against BTC, never tested for stocks."

SPY (S&P 500 ETF) is the natural stock-market equivalent of BTC as a
market-wide regime proxy -- same role (broad, liquid, widely tracked
benchmark for the asset class), not a stretch the way applying BTC
itself to equities would be. Same train/test discipline, and the same
90-day window stock_optimize.py already established is needed for a
trustworthy sample size on stocks (30 days wasn't enough --
STOCK_OPTIMIZATION_LOG.md 2026-08-26/27).
"""

from tabulate import tabulate

import stock_backtest
import optimize
from regime_filter_test import build_regime_filters, VOLATILITY_THRESHOLD_PCT


REGIME_TEST_DAYS = 90


def run():

    symbols = stock_backtest.exchange.get_markets()[:stock_backtest.SYMBOL_LIMIT]

    print(f"Loading cached stock history for {len(symbols)} symbols ({REGIME_TEST_DAYS} days)...")

    stock_cache = {}

    for symbol in symbols:
        stock_cache[symbol] = stock_backtest.fetch_history(symbol, days=REGIME_TEST_DAYS)

    print("Loading SPY history (market-wide regime proxy)...")

    spy_candles = stock_cache.get("SPY") or stock_backtest.fetch_history("SPY", days=REGIME_TEST_DAYS)

    volatility_only, volatility_and_trend = build_regime_filters(
        spy_candles, VOLATILITY_THRESHOLD_PCT,
    )

    split_ts = optimize.compute_split_ts(stock_cache)

    configs = [
        ("No filter (current live)", None),
        ("Volatility only", volatility_only),
        ("Volatility + trend", volatility_and_trend),
    ]

    rows = []

    for tag, regime_fn in configs:

        trades = stock_backtest.run_backtest(
            symbols=symbols, days=REGIME_TEST_DAYS, candle_cache=stock_cache,
            verbose=False, regime_ok_fn=regime_fn,
        )

        train, test = optimize.split_trades(trades, split_ts)

        train_stats = optimize.summarise(train)
        test_stats = optimize.summarise(test)

        rows.append([
            tag,
            train_stats["count"], f"{train_stats['win_rate']:.1f}%", f"{train_stats['expectancy']:+.3f}%",
            test_stats["count"], f"{test_stats['win_rate']:.1f}%", f"{test_stats['expectancy']:+.3f}%",
        ])

    print("\n" + "=" * 100)
    print(f"STOCK REGIME FILTER TEST (SPY volatility < {VOLATILITY_THRESHOLD_PCT}%, trend = SPY price > EMA-slow)")
    print("=" * 100)
    print(tabulate(
        rows,
        headers=["Config", "Train N", "Train WR", "Train Exp", "Test N", "Test WR", "Test Exp"],
    ))
    print("=" * 100)


if __name__ == "__main__":
    run()
