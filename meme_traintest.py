"""
=========================================
ATLAS AI
Meme Coin Train/Test Validation
=========================================

Same discipline as crypto/stocks: never trust a full-window backtest
without checking it holds up on a held-out period the tuning never
saw. Reuses optimize.py's compute_split_ts/split_trades directly
since both are generic over any {symbol: candles} cache -- not
crypto-specific.

Caveat specific to meme coins: candle history length is uneven across
symbols (see meme_backtest.py's Binance/Kraken hybrid fetch). Symbols
sourced from Kraken natively only span ~2.5 days, so their entire
history falls inside the test window and they contribute zero train
trades. That's disclosed in the report, not hidden.
"""

from meme_backtest import fetch_history, run_backtest as meme_run_backtest
from meme_exchange import exchange as meme_exchange
from optimize import compute_split_ts, split_trades, summarise
from config import MEME_SCAN_LIMIT


def main():

    symbols = meme_exchange.get_markets()[:MEME_SCAN_LIMIT]

    print(f"Fetching history for {len(symbols)} meme coin symbols...\n")

    candle_cache = {}

    for symbol in symbols:
        candle_cache[symbol] = fetch_history(symbol, days=30)

    split_ts = compute_split_ts(candle_cache)

    import datetime
    split_dt = datetime.datetime.fromtimestamp(split_ts / 1000, datetime.timezone.utc)
    print(f"Train/test split boundary: {split_dt} UTC (last 25% of window held out)\n")

    trades = meme_run_backtest(
        symbols=symbols,
        candle_cache=candle_cache,
        verbose=True,
    )

    train_trades, test_trades = split_trades(trades, split_ts)

    train_stats = summarise(train_trades)
    test_stats = summarise(test_trades)

    # How many symbols' entire history falls inside the test window
    # (short Kraken-native history), vs symbols that have real train
    # coverage (deep Binance history).
    train_only_symbols = set()
    for t in train_trades:
        train_only_symbols.add(t["symbol"])
    test_only_symbols = set()
    for t in test_trades:
        test_only_symbols.add(t["symbol"])
    no_train_coverage = test_only_symbols - train_only_symbols

    print("\n" + "=" * 70)
    print("             MEME COIN TRAIN / TEST VALIDATION")
    print("=" * 70)
    print(f"\nTRAIN  : {train_stats['count']} trades, "
          f"win rate {train_stats['win_rate']:.1f}%, "
          f"expectancy {train_stats['expectancy']:+.3f}%/trade")
    print(f"TEST   : {test_stats['count']} trades, "
          f"win rate {test_stats['win_rate']:.1f}%, "
          f"expectancy {test_stats['expectancy']:+.3f}%/trade")

    if no_train_coverage:
        print(
            f"\nNote: {len(no_train_coverage)} symbols have zero train-period "
            f"coverage (Kraken-native short history only, entirely inside "
            f"the test window): {sorted(no_train_coverage)}"
        )

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
