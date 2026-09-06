"""
=========================================
ATLAS AI
Shared Reporting Utilities
=========================================

Generic over any book's (trades, equity_rows) -- same precedent as
optimize.py's compute_split_ts/summarise/split_trades being reused
across crypto/stock/meme research rather than reimplemented per book.
This is read-only reporting/formatting, not trading decision logic,
so sharing it doesn't compromise the deliberate full independence
between books' live trading code.
"""

import re


PNL_PATTERN = re.compile(r"P&L=(-?\d+\.\d+)")


def full_trade_history(trades):
    """
    Every BUY/SELL row (as already filtered by each book's
    load_trades()), newest first, with P&L/exit-reason parsed out of
    SELL rows. This is the literal, complete trade log -- not a
    "recent N" slice.
    """

    history = []

    for row in trades:

        pnl = None
        reason = None

        if row["Decision"] == "SELL":

            match = PNL_PATTERN.search(row["Message"])

            if match:
                pnl = float(match.group(1))

            if "Reason=" in row["Message"]:
                reason = row["Message"].split("Reason=")[1].split(" |")[0]

        history.append({
            "date": row["Date"],
            "time": row["Time"],
            "symbol": row["Symbol"],
            "decision": row["Decision"],
            "price": row["Price"],
            "pnl": pnl,
            "reason": reason,
        })

    return list(reversed(history))


def group_by_period(equity_rows, period="day"):
    """
    Period-over-period equity change -- 'day' groups by calendar date,
    'month' by year-month, 'year' by year. Each period's return is
    measured against the PREVIOUS period's closing equity (not its own
    opening snapshot), matching how "today's P&L" is normally meant --
    change since yesterday's close, not since the first snapshot
    logged today. Returns oldest-first.
    """

    if not equity_rows:
        return []

    key_length = {"day": 10, "month": 7, "year": 4}[period]

    groups = {}
    order = []

    for row in equity_rows:

        key = row["Date"][:key_length]

        if key not in groups:
            groups[key] = []
            order.append(key)

        groups[key].append(row)

    results = []
    previous_close = None

    for key in order:

        rows = groups[key]

        start_equity = float(rows[0]["TotalEquity"])
        end_equity = float(rows[-1]["TotalEquity"])

        baseline = previous_close if previous_close is not None else start_equity

        pnl = end_equity - baseline
        pnl_pct = (pnl / baseline * 100) if baseline else 0.0

        results.append({
            "period": key,
            "start_equity": start_equity,
            "end_equity": end_equity,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        })

        previous_close = end_equity

    return results
