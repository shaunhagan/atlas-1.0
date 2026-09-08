"""
=========================================
ATLAS AI
Stock VWAP + Gap-Pullback Train/Test Validation
=========================================

Same discipline as every other strategy tested in this project: never
trust a full-window number without a held-out check. 90-day window,
same as mean-reversion needed for an adequate sample (stocks trade far
fewer hours/week than crypto).
"""

from tabulate import tabulate

import stock_backtest
import stock_vwap_gap_backtest as vwap_gap
import optimize


VALIDATION_DAYS = 90


def main():

    symbols = stock_backtest.exchange.get_markets()[:stock_backtest.SYMBOL_LIMIT]

    print(f"Universe: {symbols}\n")
    print(f"Fetching {VALIDATION_DAYS} days of history for {len(symbols)} symbols...\n")

    candle_cache = {}

    for symbol in symbols:
        candle_cache[symbol] = stock_backtest.fetch_history(symbol, days=VALIDATION_DAYS)

    trades = vwap_gap.run_backtest(
        symbols=symbols, days=VALIDATION_DAYS, candle_cache=candle_cache, verbose=True,
    )

    vwap_gap.print_backtest_report(trades)

    split_ts = optimize.compute_split_ts(candle_cache)

    train, test = optimize.split_trades(trades, split_ts)

    train_stats = optimize.summarise(train)
    test_stats = optimize.summarise(test)

    print("\n" + "=" * 70)
    print("STOCK VWAP+GAP TRAIN/TEST VALIDATION (90 days)")
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
