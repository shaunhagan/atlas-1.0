"""
=========================================
ATLAS AI
Strategy Drift Check
=========================================

Every strategy in this project was validated ONCE, then deployed with
fixed settings that only get re-checked when someone happens to dig
back into a specific log. Professional systems use walk-forward
re-optimization -- a standing cadence of re-validating against rolling
recent data, so drift gets caught systematically rather than by luck.

This is a lightweight version of that idea: re-run each book's CURRENT
live configuration against its most recent backtest window and report
whether it still shows positive expectancy, without changing anything.
Purely diagnostic -- flags drift, doesn't act on it. Meant to be run
periodically (manually, or on a schedule) rather than after every
single check-in.

Crypto is included for visibility even though its live settings are
intentionally not touched by anyone else in this project right now --
reading/reporting on it doesn't change its behaviour.
"""

from tabulate import tabulate

import backtest
import stock_backtest
import stock_meanrev_backtest
import meme_backtest
import optimize


def _verdict(expectancy):

    if expectancy > 0.1:
        return "OK"

    if expectancy > -0.1:
        return "WATCH (near zero)"

    return "DRIFT -- negative"


def check_crypto():

    symbols = backtest.exchange.get_markets()[:backtest.SYMBOL_LIMIT]

    candle_cache = {s: backtest.fetch_history(s, days=30) for s in symbols}

    trades = backtest.run_backtest(symbols=symbols, candle_cache=candle_cache, verbose=False)

    split_ts = optimize.compute_split_ts(candle_cache)
    _, test = optimize.split_trades(trades, split_ts)
    stats = optimize.summarise(test)

    return ["Crypto (trend engine, live)", stats["count"], f"{stats['win_rate']:.1f}%",
            f"{stats['expectancy']:+.3f}%", _verdict(stats["expectancy"])]


def check_stocks():

    symbols = stock_backtest.exchange.get_markets()[:stock_backtest.SYMBOL_LIMIT]

    candle_cache = {s: stock_backtest.fetch_history(s, days=90) for s in symbols}

    trades = stock_meanrev_backtest.run_backtest(
        symbols=symbols, days=90, candle_cache=candle_cache, verbose=False,
    )

    split_ts = optimize.compute_split_ts(candle_cache)
    _, test = optimize.split_trades(trades, split_ts)
    stats = optimize.summarise(test)

    return ["Stocks (mean reversion, live)", stats["count"], f"{stats['win_rate']:.1f}%",
            f"{stats['expectancy']:+.3f}%", _verdict(stats["expectancy"])]


def check_meme():

    symbols = meme_backtest.exchange.get_markets()

    candle_cache = {s: meme_backtest.fetch_history(s, days=30) for s in symbols}

    trades = meme_backtest.run_backtest(symbols=symbols, candle_cache=candle_cache, verbose=False)

    split_ts = optimize.compute_split_ts(candle_cache)
    _, test = optimize.split_trades(trades, split_ts)
    stats = optimize.summarise(test)

    return ["Meme (trend engine, live)", stats["count"], f"{stats['win_rate']:.1f}%",
            f"{stats['expectancy']:+.3f}%", _verdict(stats["expectancy"])]


def main():

    print("Re-validating each book's CURRENT live settings against its most "
          "recent backtest window (held-out test period only)...\n")

    rows = []

    for label, check_fn in [("crypto", check_crypto), ("stocks", check_stocks), ("meme", check_meme)]:

        print(f"Checking {label}...")

        try:
            rows.append(check_fn())
        except Exception as error:
            rows.append([label, "-", "-", "-", f"ERROR: {error}"])

    print("\n" + "=" * 100)
    print("STRATEGY DRIFT CHECK (held-out test period, current live config)")
    print("=" * 100)
    print(tabulate(
        rows,
        headers=["Book", "Test N", "Win Rate", "Test Exp", "Verdict"],
    ))
    print("=" * 100)
    print(
        "\nThis is diagnostic only -- nothing here changes live settings. "
        "A DRIFT or WATCH verdict means the current config's recent "
        "held-out performance is weak, worth a closer look (like the "
        "checks that found the stock trend engine and meme's stop-distance "
        "bug), not an automatic signal to change anything."
    )


if __name__ == "__main__":
    main()
