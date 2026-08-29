"""
=========================================
ATLAS AI
Stock Mean-Reversion -- Second Window Check
=========================================

stock_meanrev_traintest.py's 90-day result was genuinely mixed: TRAIN
negative (-0.482%, 487 trades), TEST positive (+1.366%, 76 trades) --
the opposite of the usual overfitting shape, but a strategy whose sign
flips between cuts isn't a confirmed edge either. Before either
accepting or rejecting it, check whether the positive result replicates
on a second, non-overlapping 90-day window (90-180 days ago) -- same
approach as regime_filter_traintest.py's multi-window discipline for
crypto.
"""

from tabulate import tabulate

import stock_backtest
import stock_meanrev_backtest
import optimize


WINDOW_DAYS = 90

END_DAYS_AGO = 90


def main():

    symbols = stock_backtest.exchange.get_markets()[:stock_backtest.SYMBOL_LIMIT]

    print(f"Fetching window 2 ({END_DAYS_AGO}-{END_DAYS_AGO + WINDOW_DAYS} days ago) for {len(symbols)} symbols...\n")

    candle_cache = {}

    for symbol in symbols:
        candle_cache[symbol] = stock_backtest.fetch_history(
            symbol, days=WINDOW_DAYS, end_days_ago=END_DAYS_AGO,
        )

    trades = stock_meanrev_backtest.run_backtest(
        symbols=symbols, days=WINDOW_DAYS, candle_cache=candle_cache, verbose=True,
    )

    stock_meanrev_backtest.print_backtest_report(trades)

    split_ts = optimize.compute_split_ts(candle_cache)

    train, test = optimize.split_trades(trades, split_ts)

    train_stats = optimize.summarise(train)
    test_stats = optimize.summarise(test)

    print("\n" + "=" * 70)
    print(f"STOCK MEAN-REVERSION -- WINDOW 2 ({END_DAYS_AGO}-{END_DAYS_AGO + WINDOW_DAYS}d ago)")
    print("=" * 70)
    print(tabulate(
        [
            ["TRAIN", train_stats["count"], f"{train_stats['win_rate']:.1f}%", f"{train_stats['expectancy']:+.3f}%"],
            ["TEST (held out)", test_stats["count"], f"{test_stats['win_rate']:.1f}%", f"{test_stats['expectancy']:+.3f}%"],
        ],
        headers=["Split", "Trades", "Win Rate", "Expectancy/Trade"],
    ))
    print("=" * 70)


if __name__ == "__main__":
    main()
