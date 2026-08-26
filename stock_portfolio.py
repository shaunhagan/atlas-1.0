"""
ATLAS AI
Stock Paper Trading Portfolio

Mirrors portfolio.py exactly, pointed at a separate file and using
stock_exchange for equity pricing, so stocks and crypto have fully
independent capital and history.
"""

from pathlib import Path
import json

from config import STOCK_STARTING_BALANCE


# ============================================================
# FILE SETTINGS
# ============================================================

DATA_FOLDER = Path("data")
DATA_FOLDER.mkdir(exist_ok=True)

PORTFOLIO_FILE = DATA_FOLDER / "stock_portfolio.json"


# ============================================================
# DEFAULT PORTFOLIO
# ============================================================

DEFAULT_PORTFOLIO = {
    "balance": STOCK_STARTING_BALANCE,
    "starting_balance": STOCK_STARTING_BALANCE,
    "positions": {},
    "trade_count": 0,
    "wins": 0,
    "losses": 0,
    "realised_pnl": 0.0,
}


# ============================================================
# LOAD / SAVE
# ============================================================

def load_portfolio():
    """Load the paper portfolio from disk."""

    if not PORTFOLIO_FILE.exists():
        save_portfolio(DEFAULT_PORTFOLIO)

    with open(PORTFOLIO_FILE, "r") as file:
        portfolio = json.load(file)

    # Make sure older portfolio files have all fields.
    for key, value in DEFAULT_PORTFOLIO.items():

        if key not in portfolio:
            portfolio[key] = value

    return portfolio


def save_portfolio(portfolio):
    """Save the paper portfolio to disk."""

    with open(PORTFOLIO_FILE, "w") as file:

        json.dump(
            portfolio,
            file,
            indent=4
        )


# ============================================================
# BALANCE
# ============================================================

def get_balance():
    """Return available cash balance."""

    portfolio = load_portfolio()

    return portfolio["balance"]


def update_balance(amount):
    """Add or subtract cash from the portfolio."""

    portfolio = load_portfolio()

    portfolio["balance"] += amount

    save_portfolio(portfolio)


# ============================================================
# POSITIONS
# ============================================================

def add_position(
    symbol,
    quantity,
    entry_price,
    stop_loss=None,
    take_profit=None,
    position_value=None,
):
    """Create or replace an open paper position."""

    portfolio = load_portfolio()

    if position_value is None:
        position_value = quantity * entry_price

    portfolio["positions"][symbol] = {
        "quantity": quantity,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "position_value": position_value,
    }

    save_portfolio(portfolio)


def remove_position(symbol):
    """Remove an open paper position."""

    portfolio = load_portfolio()

    if symbol in portfolio["positions"]:
        del portfolio["positions"][symbol]

    save_portfolio(portfolio)


def has_position(symbol):
    """Return True if a symbol currently has an open position."""

    portfolio = load_portfolio()

    return symbol in portfolio["positions"]


def get_positions():
    """Return all open paper positions."""

    portfolio = load_portfolio()

    return portfolio["positions"]


# ============================================================
# TRADE RECORDING
# ============================================================

def record_trade(pnl):
    """Record a completed paper trade."""

    portfolio = load_portfolio()

    portfolio["trade_count"] += 1

    portfolio["realised_pnl"] += pnl

    if pnl > 0:

        portfolio["wins"] += 1

    elif pnl < 0:

        portfolio["losses"] += 1

    save_portfolio(portfolio)


# ============================================================
# BASIC SUMMARY
# ============================================================

def get_summary():
    """Return portfolio statistics."""

    portfolio = load_portfolio()

    return {
        "balance": portfolio["balance"],
        "starting_balance": portfolio["starting_balance"],
        "positions": portfolio["positions"],
        "trade_count": portfolio["trade_count"],
        "wins": portfolio["wins"],
        "losses": portfolio["losses"],
        "realised_pnl": portfolio["realised_pnl"],
    }


# ============================================================
# LIVE EQUITY CALCULATION
# ============================================================

def get_equity():
    """
    Calculate current paper-account equity.

    Equity =
        available cash
        +
        current market value of open positions
    """

    portfolio = load_portfolio()

    cash = float(portfolio["balance"])

    position_value = 0.0

    unrealised_pnl = 0.0

    from stock_exchange import exchange

    for symbol, position in portfolio["positions"].items():

        quantity = float(
            position.get("quantity", 0.0)
        )

        entry_price = float(
            position.get("entry_price", 0.0)
        )

        # A failed fetch for one symbol must not zero out the
        # rest of the snapshot. Fall back to entry price (zero
        # unrealised P&L for this symbol) rather than skipping
        # it, so a single transient error can't understate total
        # equity for the whole portfolio.
        current_price = entry_price

        try:

            ticker = exchange.get_ticker(symbol)

            fetched_price = ticker.get("last")

            if fetched_price is not None:
                current_price = float(fetched_price)

        except Exception as error:

            print(
                f"Equity price fetch warning for {symbol}: {error}"
            )

        current_value = quantity * current_price

        position_value += current_value

        unrealised_pnl += (
            current_price - entry_price
        ) * quantity

    total_equity = cash + position_value

    total_pnl = (
        total_equity
        - float(portfolio["starting_balance"])
    )

    return {
        "cash": cash,
        "position_value": position_value,
        "total_equity": total_equity,
        "realised_pnl": float(
            portfolio["realised_pnl"]
        ),
        "unrealised_pnl": unrealised_pnl,
        "total_pnl": total_pnl,
        "trade_count": portfolio["trade_count"],
        "wins": portfolio["wins"],
        "losses": portfolio["losses"],
        "open_positions": len(
            portfolio["positions"]
        ),
    }
