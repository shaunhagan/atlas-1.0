"""
ATLAS AI
Meme Coin Paper Trading Engine

Mirrors paper_trader.py's mechanics exactly, using meme_portfolio/
meme_logger and the MEME_* config constants -- deliberately more
aggressive settings (bigger risk per trade, wider stops, lower
confidence bar) than the "safe" crypto book, by design.
"""

import math

from config import (
    MEME_RISK_PER_TRADE,
    MEME_ATR_STOP_MULTIPLIER,
    MEME_RISK_REWARD_RATIO,
    MEME_MAX_OPEN_TRADES,
    MEME_TRADING_FRICTION_PCT,
    MEME_MIN_STOP_DISTANCE_PCT,
)

import meme_portfolio as portfolio

from meme_logger import log_trade


POSITION_ALLOCATION = 1.0 / MEME_MAX_OPEN_TRADES


def _open_position(symbol, price, confidence, atr):
    """Open a new paper BUY position."""

    if price <= 0:
        return False

    if atr is None or math.isnan(atr) or atr <= 0:
        return False

    if portfolio.has_position(symbol):
        return False

    positions = portfolio.get_positions()

    if len(positions) >= MEME_MAX_OPEN_TRADES:
        return False

    balance = portfolio.get_balance()

    if balance <= 0:
        return False

    portfolio_data = portfolio.load_portfolio()

    starting_balance = float(
        portfolio_data.get("starting_balance", balance)
    )

    fill_price = price * (1 + MEME_TRADING_FRICTION_PCT)

    stop_distance = max(
        MEME_ATR_STOP_MULTIPLIER * atr,
        fill_price * MEME_MIN_STOP_DISTANCE_PCT / 100,
    )

    stop_loss = fill_price - stop_distance

    if stop_loss <= 0:
        return False

    take_profit = fill_price + (MEME_RISK_REWARD_RATIO * stop_distance)

    risk_amount = starting_balance * MEME_RISK_PER_TRADE

    quantity = risk_amount / stop_distance

    allocation_ceiling = starting_balance * POSITION_ALLOCATION

    allocation = quantity * fill_price

    if allocation > allocation_ceiling:
        allocation = allocation_ceiling
        quantity = allocation / fill_price

    allocation = min(allocation, balance)

    quantity = allocation / fill_price

    if allocation <= 0:
        return False

    portfolio.update_balance(-allocation)

    portfolio.add_position(
        symbol=symbol,
        quantity=quantity,
        entry_price=fill_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_value=allocation,
    )

    log_trade(
        symbol, "BUY", confidence, price,
        (
            f"Paper Buy | Qty={quantity:.8f} | Value={allocation:.2f} | "
            f"SL={stop_loss:.8f} | TP={take_profit:.8f}"
        ),
    )

    print()
    print(f"MEME PAPER BUY : {symbol} @ {price:.8f} | Confidence: {confidence}%")
    print(f"    Allocation  : {allocation:.2f}")
    print(f"    Position    : {quantity:.8f}")
    print(f"    Stop Loss   : {stop_loss:.8f}")
    print(f"    Take Profit : {take_profit:.8f}")

    return True


def _close_position(symbol, price, reason="SELL", confidence=100):
    """Close an existing paper position."""

    if price <= 0:
        return False

    positions = portfolio.get_positions()

    if symbol not in positions:
        return False

    position = positions[symbol]

    quantity = float(position["quantity"])
    entry_price = float(position["entry_price"])

    fill_price = price * (1 - MEME_TRADING_FRICTION_PCT)

    proceeds = quantity * fill_price
    cost = quantity * entry_price
    pnl = proceeds - cost

    portfolio.update_balance(proceeds)
    portfolio.record_trade(pnl)
    portfolio.remove_position(symbol)

    log_trade(
        symbol, "SELL", confidence, price,
        (
            f"Paper Sell | Reason={reason} | Entry={entry_price:.8f} | "
            f"Qty={quantity:.8f} | P&L={pnl:.2f}"
        ),
    )

    print()
    print(f"MEME PAPER {reason} : {symbol} @ {price:.8f} | P&L: {pnl:+.2f}")

    return True


def check_position(symbol, current_price):
    """Check one position for automatic SL/TP exit."""

    positions = portfolio.get_positions()

    if symbol not in positions:
        return False

    if current_price is None:
        return False

    current_price = float(current_price)

    if current_price <= 0:
        return False

    position = positions[symbol]

    stop_loss = position.get("stop_loss")
    take_profit = position.get("take_profit")

    if stop_loss is not None and current_price <= float(stop_loss):
        return _close_position(symbol, current_price, "STOP LOSS", 100)

    if take_profit is not None and current_price >= float(take_profit):
        return _close_position(symbol, current_price, "TAKE PROFIT", 100)

    return False


def check_all_positions():
    """Check every open paper position."""

    positions = portfolio.get_positions()

    if not positions:
        return 0

    closed_count = 0

    try:

        from meme_exchange import exchange

        for symbol in list(positions.keys()):

            try:

                ticker = exchange.get_ticker(symbol)
                current_price = ticker.get("last")

                if check_position(symbol, current_price):
                    closed_count += 1

            except Exception as error:

                print(f"Paper exit check failed for {symbol}: {error}")

    except Exception as error:

        print(f"Paper exit check error: {error}")

    return closed_count


def execute(symbol, decision, confidence, price, atr=None):
    """Execute a paper BUY or SELL."""

    if price is None:
        return False

    try:
        price = float(price)
    except (TypeError, ValueError):
        return False

    if price <= 0:
        return False

    decision = str(decision).upper()

    if decision == "BUY":
        return _open_position(symbol, price, confidence, atr)

    if decision == "SELL":
        return _close_position(symbol, price, "SIGNAL", confidence)

    return False
