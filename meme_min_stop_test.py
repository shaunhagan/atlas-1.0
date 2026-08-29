"""
=========================================
ATLAS AI
Meme Coin Minimum Stop Distance Floor -- Validation
=========================================

Live log (2026-08-28 19:50-19:54): MUBARAK/USD opened and hit stop-loss
4 times in ~4 minutes, 2 seconds after each entry, stop distance ~0% of
price -- a near-zero live ATR reading produced a pathologically tight
bracket. meme_paper_trader.py / meme_backtest.py now floor
stop_distance at MEME_MIN_STOP_DISTANCE_PCT of fill price. This checks
which floor value (if any) actually helps out-of-sample before trusting
the 0.5% default picked as a first guess.
"""

from tabulate import tabulate

import meme_backtest
import optimize
from config import MEME_SCAN_LIMIT


TEST_DAYS = 30

MIN_STOP_DISTANCE_GRID = [0.0, 0.25, 0.5, 1.0, 1.5]


def run():

    symbols = meme_backtest.exchange.get_markets()[:MEME_SCAN_LIMIT]

    print(f"Loading cached history for {len(symbols)} symbols ({TEST_DAYS} days)...")

    candle_cache = {}

    for symbol in symbols:
        candle_cache[symbol] = meme_backtest.fetch_history(symbol, days=TEST_DAYS)

    split_ts = optimize.compute_split_ts(candle_cache)

    rows = []

    for floor in MIN_STOP_DISTANCE_GRID:

        trades = meme_backtest.run_backtest(
            symbols=symbols, days=TEST_DAYS, candle_cache=candle_cache,
            verbose=False, min_stop_distance_pct=floor,
        )

        train, test = optimize.split_trades(trades, split_ts)

        train_stats = optimize.summarise(train)
        test_stats = optimize.summarise(test)

        rows.append([
            f"{floor}%",
            train_stats["count"], f"{train_stats['win_rate']:.1f}%", f"{train_stats['expectancy']:+.3f}%",
            test_stats["count"], f"{test_stats['win_rate']:.1f}%", f"{test_stats['expectancy']:+.3f}%",
        ])

    print("\n" + "=" * 100)
    print("MEME COIN MIN STOP DISTANCE FLOOR -- TRAIN/TEST")
    print("=" * 100)
    print(tabulate(
        rows,
        headers=["Floor", "Train N", "Train WR", "Train Exp", "Test N", "Test WR", "Test Exp"],
    ))
    print("=" * 100)


if __name__ == "__main__":
    run()
