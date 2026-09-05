"""
=========================================
ATLAS AI
Risk Guards -- Daily Loss Circuit Breaker + Portfolio Heat Gate
=========================================

Asset-agnostic: works for crypto, stocks, and meme, each maintaining
its own in-memory state (keyed by label, so books never share or
clobber each other's state even though they call the same functions
from separate processes -- each process has its own module state).
Gate new entries only, never exits -- same principle as every other
filter in this project (volatility regime gate, the rejected HTF
confirmation).
"""

from datetime import datetime


_day_start_equity = {}
_day_start_date = {}


def check_daily_loss_limit(portfolio_module, label, limit_pct):
    """
    Returns True (ok to open new positions) or False (today's
    drawdown from this book's day-start equity baseline has reached
    limit_pct). The baseline resets at the first check of each new
    calendar day, using whatever the equity is at that moment -- if
    the process restarts mid-day, the baseline re-anchors from the
    restart point rather than losing track of the original day-start
    value. Acceptable trade-off for simplicity over a persisted
    baseline file.
    """

    try:

        today = datetime.now().strftime("%Y-%m-%d")

        equity = portfolio_module.get_equity()

        current_equity = float(equity["total_equity"])

        if _day_start_date.get(label) != today:

            _day_start_date[label] = today
            _day_start_equity[label] = current_equity

        baseline = _day_start_equity[label]

        if baseline <= 0:
            return True

        drawdown_pct = (baseline - current_equity) / baseline * 100

        return drawdown_pct < limit_pct

    except Exception as error:

        print(
            f"Daily loss check error for {label} "
            f"(defaulting to allow): {error}"
        )

        return True


def check_portfolio_heat(
    portfolio_module,
    exchange_module,
    label,
    min_positions_for_heat=4,
    loss_fraction_threshold=0.6,
):
    """
    Returns True (ok to open new positions) or False (the book is
    "hot" -- most of what's already open is underwater right now, a
    sign of a correlated/systemic move rather than independent
    per-symbol noise).

    Directly motivated by meme's 2026-08-28/30 drawdown: 16 of 18
    traded coins were net negative at once, a correlated move a
    position-COUNT cap (MAX_OPEN_TRADES) gives no protection against,
    since it isn't designed to. Validated via portfolio_backtest.py's
    shared-state engine before deploying (meme_portfolio_heat_test.py,
    stock_portfolio_heat_test.py) -- the per-symbol independent
    backtesters can't test this at all, having no concept of
    concurrently open positions.

    Below min_positions_for_heat open, always allows -- too small a
    sample to mean anything about the book as a whole.
    """

    try:

        positions = portfolio_module.get_positions()

        if len(positions) < min_positions_for_heat:
            return True

        underwater = 0

        for symbol, position in positions.items():

            entry_price = float(position.get("entry_price", 0.0))

            if entry_price <= 0:
                continue

            current_price = entry_price

            try:

                ticker = exchange_module.get_ticker(symbol)
                fetched_price = ticker.get("last")

                if fetched_price is not None:
                    current_price = float(fetched_price)

            except Exception:
                pass

            if current_price < entry_price:
                underwater += 1

        fraction_underwater = underwater / len(positions)

        return fraction_underwater < loss_fraction_threshold

    except Exception as error:

        print(
            f"Portfolio heat check error for {label} "
            f"(defaulting to allow): {error}"
        )

        return True
