"""
=========================================
ATLAS AI
Daily Loss Circuit Breaker
=========================================

Asset-agnostic: works for both crypto and stocks, each maintaining
its own in-memory day-start equity baseline (keyed by label, so the
two books never share or clobber each other's state even though they
call the same function from separate processes -- each process has
its own module state). Gates new entries only, never exits -- same
principle as every other filter in this project (volatility regime
gate, the rejected HTF confirmation).
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
