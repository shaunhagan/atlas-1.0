"""
=========================================
ATLAS AI
Meme Coin Regime Filter Test
=========================================

The volatility regime filter (BTC realised volatility as a market-wide
risk proxy) is validated and LIVE for crypto (regime_filter_traintest.py,
OPTIMIZATION_LOG.md 2026-08-23) and was deliberately left OFF for the
meme tier at launch -- meme_scanner.py's execute_paper_trades() has no
regime/HTF gate by design, the aggressive tier.

That was a reasonable default, not a tested one. Meme coins are
typically even more sentiment-driven than large caps, so a market-wide
risk-off gate might matter MORE here, not less -- worth actually
checking rather than assuming the crypto result (or its absence)
transfers. Same train/test discipline as everywhere else in this repo.
"""

import pandas as pd
from tabulate import tabulate

import backtest
import meme_backtest
import optimize
from regime_filter_test import build_regime_filters, VOLATILITY_THRESHOLD_PCT
from config import MEME_SCAN_LIMIT


REGIME_TEST_DAYS = 30


def run():

    symbols = meme_backtest.exchange.get_markets()[:MEME_SCAN_LIMIT]

    print(f"Loading cached meme coin history for {len(symbols)} symbols ({REGIME_TEST_DAYS} days)...")

    meme_cache = {}

    for symbol in symbols:
        meme_cache[symbol] = meme_backtest.fetch_history(symbol, days=REGIME_TEST_DAYS)

    print("Loading BTC/USDT history (market-wide regime proxy, Binance-sourced)...")

    btc_candles = backtest.fetch_history("BTC/USDT", days=REGIME_TEST_DAYS)

    volatility_only, volatility_and_trend = build_regime_filters(
        btc_candles, VOLATILITY_THRESHOLD_PCT,
    )

    split_ts = optimize.compute_split_ts(meme_cache)

    configs = [
        ("No filter (current live)", None),
        ("Volatility only", volatility_only),
        ("Volatility + trend", volatility_and_trend),
    ]

    rows = []

    for tag, regime_fn in configs:

        trades = meme_backtest.run_backtest(
            symbols=symbols, days=REGIME_TEST_DAYS, candle_cache=meme_cache,
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
    print(f"MEME COIN REGIME FILTER TEST (BTC volatility < {VOLATILITY_THRESHOLD_PCT}%, trend = BTC price > EMA-slow)")
    print("=" * 100)
    print(tabulate(
        rows,
        headers=["Config", "Train N", "Train WR", "Train Exp", "Test N", "Test WR", "Test Exp"],
    ))
    print("=" * 100)


if __name__ == "__main__":
    run()
