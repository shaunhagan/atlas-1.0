"""
ATLAS AI
Paper Trading Engine
"""

import math

from config import (
    RISK_PER_TRADE,
    ATR_STOP_MULTIPLIER,
    RISK_REWARD_RATIO,
    MAX_OPEN_TRADES,
    TRADING_FRICTION_PCT,
)

import portfolio

from logger import log_trade


# ============================================================
# PAPER PORTFOLIO SETTINGS
# ============================================================

POSITION_ALLOCATION = 1.0 / MAX_OPEN_TRADES


# ============================================================
# OPEN PAPER POSITION
# ============================================================

def _open_position(symbol, price, confidence, atr):
    """Open a new paper BUY position.

    Position size is risk-based: it risks a fixed fraction of
    starting balance (RISK_PER_TRADE) on the ATR-derived stop
    distance, so volatile symbols get a proportionally smaller
    quantity than calm ones for the same dollar risk. The result
    is capped at the old fixed per-slot allocation ceiling so a
    very low-ATR symbol can't dominate the book.
    """

    if price <= 0:
        return False

    if atr is None or math.isnan(atr) or atr <= 0:
        return False

    if portfolio.has_position(symbol):
        return False

    positions = portfolio.get_positions()

    if len(positions) >= MAX_OPEN_TRADES:
        return False

    balance = portfolio.get_balance()

    if balance <= 0:
        return False

    portfolio_data = portfolio.load_portfolio()

    starting_balance = float(
        portfolio_data.get(
            "starting_balance",
            balance,
        )
    )

    # Fill price is worse than the quoted price by the assumed
    # fee + slippage friction -- entry_price/stop/take-profit are
    # all anchored to this true cost basis, not the raw quote.
    fill_price = price * (1 + TRADING_FRICTION_PCT)

    stop_distance = ATR_STOP_MULTIPLIER * atr

    stop_loss = fill_price - stop_distance

    if stop_loss <= 0:
        return False

    take_profit = fill_price + (
        RISK_REWARD_RATIO * stop_distance
    )

    risk_amount = starting_balance * RISK_PER_TRADE

    quantity = risk_amount / stop_distance

    allocation_ceiling = (
        starting_balance
        * POSITION_ALLOCATION
    )

    allocation = quantity * fill_price

    if allocation > allocation_ceiling:
        allocation = allocation_ceiling
        quantity = allocation / fill_price

    allocation = min(
        allocation,
        balance,
    )

    quantity = allocation / fill_price

    if allocation <= 0:
        return False

    # Reserve paper cash.
    portfolio.update_balance(
        -allocation
    )

    # Save the position.
    portfolio.add_position(
        symbol=symbol,
        quantity=quantity,
        entry_price=fill_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_value=allocation,
    )

    # --------------------------------------------------------
    # LOG BUY
    # --------------------------------------------------------

    log_trade(
        symbol,
        "BUY",
        confidence,
        price,
        (
            f"Paper Buy | "
            f"Qty={quantity:.8f} | "
            f"Value={allocation:.2f} | "
            f"SL={stop_loss:.8f} | "
            f"TP={take_profit:.8f}"
        ),
    )

    print()
    print(
        f"PAPER BUY : {symbol} @ {price:.6f} "
        f"| Confidence: {confidence}%"
    )

    print(
        f"    Allocation  : {allocation:.2f}"
    )

    print(
        f"    Position    : {quantity:.8f}"
    )

    print(
        f"    Stop Loss   : {stop_loss:.6f}"
    )

    print(
        f"    Take Profit : {take_profit:.6f}"
    )

    return True


# ============================================================
# CLOSE PAPER POSITION
# ============================================================

def _close_position(
    symbol,
    price,
    reason="SELL",
    confidence=100,
):
    """Close an existing paper position."""

    if price <= 0:
        return False

    positions = portfolio.get_positions()

    if symbol not in positions:
        return False

    position = positions[symbol]

    quantity = float(
        position["quantity"]
    )

    entry_price = float(
        position["entry_price"]
    )

    # Exit fill is worse than the quoted price by the same
    # friction assumption applied on entry.
    fill_price = price * (1 - TRADING_FRICTION_PCT)

    proceeds = quantity * fill_price

    cost = quantity * entry_price

    pnl = proceeds - cost

    # Return complete sale proceeds.
    portfolio.update_balance(
        proceeds
    )

    # Record completed trade.
    portfolio.record_trade(
        pnl
    )

    # Remove position.
    portfolio.remove_position(
        symbol
    )

    # --------------------------------------------------------
    # LOG SELL
    # --------------------------------------------------------

    log_trade(
        symbol,
        "SELL",
        confidence,
        price,
        (
            f"Paper Sell | "
            f"Reason={reason} | "
            f"Entry={entry_price:.8f} | "
            f"Qty={quantity:.8f} | "
            f"P&L={pnl:.2f}"
        ),
    )

    print()
    print(
        f"PAPER {reason} : "
        f"{symbol} @ {price:.6f} "
        f"| P&L: {pnl:+.2f}"
    )

    return True


# ============================================================
# CHECK ONE POSITION
# ============================================================

def check_position(
    symbol,
    current_price,
):
    """Check one position for automatic SL/TP exit."""

    positions = portfolio.get_positions()

    if symbol not in positions:
        return False

    if current_price is None:
        return False

    current_price = float(
        current_price
    )

    if current_price <= 0:
        return False

    position = positions[symbol]

    stop_loss = position.get(
        "stop_loss"
    )

    take_profit = position.get(
        "take_profit"
    )

    # --------------------------------------------------------
    # STOP LOSS
    # --------------------------------------------------------

    if (
        stop_loss is not None
        and current_price <= float(stop_loss)
    ):

        return _close_position(
            symbol,
            current_price,
            "STOP LOSS",
            100,
        )

    # --------------------------------------------------------
    # TAKE PROFIT
    # --------------------------------------------------------

    if (
        take_profit is not None
        and current_price >= float(take_profit)
    ):

        return _close_position(
            symbol,
            current_price,
            "TAKE PROFIT",
            100,
        )

    return False


# ============================================================
# CHECK ALL POSITIONS
# ============================================================

def check_all_positions():
    """Check every open paper position."""

    positions = portfolio.get_positions()

    if not positions:
        return 0

    closed_count = 0

    try:

        from exchange import exchange

        for symbol in list(
            positions.keys()
        ):

            try:

                ticker = exchange.get_ticker(
                    symbol
                )

                current_price = ticker.get(
                    "last"
                )

                if check_position(
                    symbol,
                    current_price,
                ):

                    closed_count += 1

            except Exception as error:

                print(
                    f"Paper exit check failed "
                    f"for {symbol}: {error}"
                )

    except Exception as error:

        print(
            f"Paper exit check error: {error}"
        )

    return closed_count


# ============================================================
# EXECUTE PAPER TRADE
# ============================================================

def execute(
    symbol,
    decision,
    confidence,
    price,
    atr=None,
):
    """Execute a paper BUY or SELL."""

    if price is None:
        return False

    try:

        price = float(price)

    except (
        TypeError,
        ValueError,
    ):

        return False

    if price <= 0:
        return False

    decision = str(
        decision
    ).upper()

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    if decision == "BUY":

        return _open_position(
            symbol,
            price,
            confidence,
            atr,
        )

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    if decision == "SELL":

        return _close_position(
            symbol,
            price,
            "SIGNAL",
            confidence,
        )

    return False