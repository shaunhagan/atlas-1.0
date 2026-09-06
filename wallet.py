"""
=========================================
ATLAS AI
Paper Wallet Ledger
=========================================

A real, functioning ledger for simulated capital -- not a fabricated
demo. Deposits/withdrawals call each book's own, already-existing
update_balance() (the same function paper_trader.py uses to move cash
when opening/closing positions), so this doesn't introduce new
trading-state-mutation logic, just a new caller of an existing one.

Explicitly, unambiguously PAPER money: there is no live trading tier
in this project, no payment processor, no bank connection. Every
figure here is simulated capital, and every page that shows it labels
it that way -- see the .mode-paper banner used throughout the wallet
UI. Never conflate this with real funds.

Note on returns: a deposit/withdrawal changes a book's cash balance
directly. It is NOT backed out of that book's "Total Return %" (which
is still computed, as everywhere else in this project, from the
book's very first ever equity snapshot) -- so a deposit will show up
as a jump in the equity curve, same as a real brokerage statement
shows a cash-flow event distinctly from trading gains. Disclosed on
the wallet page rather than silently smoothed over.
"""

import json
from datetime import datetime
from pathlib import Path


DATA_FOLDER = Path("data")
DATA_FOLDER.mkdir(exist_ok=True)

LEDGER_FILE = DATA_FOLDER / "wallet_ledger.json"


def _load_ledger():

    if not LEDGER_FILE.exists():
        return []

    try:
        with open(LEDGER_FILE, "r", encoding="utf-8") as file:
            return json.load(file).get("transactions", [])
    except Exception:
        return []


def _save_ledger(transactions):

    with open(LEDGER_FILE, "w", encoding="utf-8") as file:
        json.dump({"transactions": transactions}, file, indent=2)


def _record(book_key, book_label, ttype, amount, balance_after, status):

    transactions = _load_ledger()

    transactions.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "book_key": book_key,
        "book_label": book_label,
        "type": ttype,
        "amount": amount,
        "balance_after": balance_after,
        "status": status,
    })

    _save_ledger(transactions)


def load_transactions(limit=None):
    """Newest first."""

    transactions = list(reversed(_load_ledger()))

    return transactions[:limit] if limit else transactions


def deposit(portfolio_module, book_key, book_label, amount):
    """Add simulated cash to a book. Returns (ok, message)."""

    if amount is None or amount <= 0:
        return False, "Deposit amount must be a positive number."

    portfolio_module.update_balance(amount)

    new_balance = portfolio_module.get_balance()

    _record(book_key, book_label, "deposit", amount, new_balance, "completed")

    return True, f"Deposited ${amount:,.2f} of paper capital into {book_label}."


def withdraw(portfolio_module, book_key, book_label, amount):
    """Remove simulated cash from a book, if enough is free (not tied
    up in open positions). Returns (ok, message)."""

    if amount is None or amount <= 0:
        return False, "Withdrawal amount must be a positive number."

    available = portfolio_module.get_balance()

    if amount > available:

        _record(book_key, book_label, "withdrawal", amount, available, "rejected")

        return False, (
            f"Cannot withdraw ${amount:,.2f} -- only ${available:,.2f} is "
            f"free (not tied up in open positions) in {book_label}."
        )

    portfolio_module.update_balance(-amount)

    new_balance = portfolio_module.get_balance()

    _record(book_key, book_label, "withdrawal", amount, new_balance, "completed")

    return True, f"Withdrew ${amount:,.2f} of paper capital from {book_label}."
