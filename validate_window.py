"""
=========================================
ATLAS AI
Second Historical Window Validation
=========================================

Everything validated so far (see OPTIMIZATION_LOG.md) comes from one
30-day window, with a train/test split inside that same window. This
tests the current live config against a second, non-overlapping
30-day window ending 35 days ago (a 5-day gap from the primary
window's start, so there's no overlap at all) -- the cheapest
available guard against the whole result set being an artifact of
one unusual month.
"""

from tabulate import tabulate

import backtest


VALIDATION_SYMBOL_LIMIT = 40

WINDOW_DAYS = 30

WINDOW_END_DAYS_AGO = 35


def run_validation():

    symbols = backtest.exchange.get_markets()[:VALIDATION_SYMBOL_LIMIT]

    print(
        f"Validating current live config on a second window: "
        f"{WINDOW_DAYS} days ending {WINDOW_END_DAYS_AGO} days ago "
        f"({len(symbols)} symbols)...\n"
    )

    cache = {}

    for symbol in symbols:
        cache[symbol] = backtest.fetch_history(
            symbol,
            days=WINDOW_DAYS,
            end_days_ago=WINDOW_END_DAYS_AGO,
        )

    trades = backtest.run_backtest(
        symbols=symbols,
        candle_cache=cache,
        verbose=False,
    )

    wins = [t for t in trades if t["pnl_pct"] > 0]

    win_rate = len(wins) / len(trades) * 100 if trades else 0.0

    expectancy = (
        sum(t["pnl_pct"] for t in trades) / len(trades)
        if trades else 0.0
    )

    print(tabulate(
        [["Second window (current live config)", len(trades), f"{win_rate:.1f}%", f"{expectancy:+.3f}%"]],
        headers=["Config", "Trades", "Win Rate", "Expectancy/Trade"],
    ))


if __name__ == "__main__":
    run_validation()
