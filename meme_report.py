"""
=========================================
ATLAS AI
Meme Coin Performance Report
=========================================

Mirrors report.py exactly, reading the separate meme coin logs/portfolio.
"""

import csv
import re
from pathlib import Path

from tabulate import tabulate

import meme_portfolio as portfolio


LOG_FOLDER = Path("logs")

TRADE_LOG = LOG_FOLDER / "meme_atlas_log.csv"

EQUITY_LOG = LOG_FOLDER / "meme_equity_log.csv"

PNL_PATTERN = re.compile(r"P&L=(-?\d+\.\d+)")


def load_trades():
    """Load raw trade log rows."""

    if not TRADE_LOG.exists():
        return []

    with open(TRADE_LOG, "r", encoding="utf-8") as file:

        reader = csv.DictReader(file)

        return [
            row for row in reader
            if row.get("Decision") in ("BUY", "SELL")
        ]


def load_equity_curve():
    """Load equity snapshot rows."""

    if not EQUITY_LOG.exists():
        return []

    with open(EQUITY_LOG, "r", encoding="utf-8") as file:

        reader = csv.DictReader(file)

        return list(reader)


def summarise_trades(trades):
    """Extract closed-trade P&L and exit reason from SELL rows."""

    closed = []

    for row in trades:

        if row["Decision"] != "SELL":
            continue

        match = PNL_PATTERN.search(row["Message"])

        if not match:
            continue

        reason = "UNKNOWN"

        if "Reason=" in row["Message"]:
            reason = row["Message"].split("Reason=")[1].split(" |")[0]

        closed.append({
            "symbol": row["Symbol"],
            "pnl": float(match.group(1)),
            "reason": reason,
        })

    wins = [trade for trade in closed if trade["pnl"] > 0]
    losses = [trade for trade in closed if trade["pnl"] < 0]

    return closed, wins, losses


def max_drawdown(equity_rows):
    """Largest peak-to-trough drop in the equity curve, as a percentage."""

    if not equity_rows:
        return 0.0

    peak = float(equity_rows[0]["TotalEquity"])
    worst = 0.0

    for row in equity_rows:

        value = float(row["TotalEquity"])

        peak = max(peak, value)

        if peak > 0:
            drawdown = (peak - value) / peak * 100
            worst = max(worst, drawdown)

    return worst


def print_report():

    print()
    print("=" * 70)
    print("              ATLAS AI - MEME COIN PERFORMANCE REPORT")
    print("=" * 70)

    summary = portfolio.get_summary()
    trades = load_trades()
    equity_rows = load_equity_curve()

    closed, wins, losses = summarise_trades(trades)

    print()
    print(f"Starting Balance : {summary['starting_balance']:.2f}")
    print(f"Current Balance  : {summary['balance']:.2f}")
    print(f"Realised P&L     : {summary['realised_pnl']:+.2f}")
    print(f"Open Positions   : {len(summary['positions'])}")

    if equity_rows:

        first_equity = float(equity_rows[0]["TotalEquity"])
        last_equity = float(equity_rows[-1]["TotalEquity"])

        total_return_pct = (
            (last_equity / first_equity - 1) * 100
            if first_equity else 0.0
        )

        print()
        print(f"Equity Snapshots : {len(equity_rows)}")
        print(f"First Equity     : {first_equity:.2f}")
        print(f"Latest Equity    : {last_equity:.2f}")
        print(f"Total Return     : {total_return_pct:+.2f}%")
        print(f"Max Drawdown     : {max_drawdown(equity_rows):.2f}%")

    else:

        print()
        print("No equity snapshots recorded yet.")

    print()
    print(f"Closed Trades    : {len(closed)}")

    if closed:

        win_rate = len(wins) / len(closed) * 100

        avg_win = (
            sum(trade["pnl"] for trade in wins) / len(wins)
            if wins else 0.0
        )

        avg_loss = (
            sum(trade["pnl"] for trade in losses) / len(losses)
            if losses else 0.0
        )

        print(
            f"Win Rate         : {win_rate:.1f}% "
            f"({len(wins)}W / {len(losses)}L)"
        )
        print(f"Average Win      : {avg_win:+.2f}")
        print(f"Average Loss     : {avg_loss:+.2f}")

        ranked = sorted(closed, key=lambda trade: trade["pnl"], reverse=True)

        print()
        print("Top 5 Winners")
        print(tabulate(
            [
                [trade["symbol"], trade["reason"], f"{trade['pnl']:+.2f}"]
                for trade in ranked[:5]
            ],
            headers=["Symbol", "Exit Reason", "P&L"],
        ))

        print()
        print("Top 5 Losers")
        print(tabulate(
            [
                [trade["symbol"], trade["reason"], f"{trade['pnl']:+.2f}"]
                for trade in ranked[-5:][::-1]
            ],
            headers=["Symbol", "Exit Reason", "P&L"],
        ))

        reason_counts = {}

        for trade in closed:
            reason_counts[trade["reason"]] = reason_counts.get(trade["reason"], 0) + 1

        print()
        print("Exit Reasons")
        print(tabulate(
            [[reason, count] for reason, count in reason_counts.items()],
            headers=["Reason", "Count"],
        ))

    else:

        print("No closed trades yet.")

    print()
    print("=" * 70)


if __name__ == "__main__":
    print_report()
