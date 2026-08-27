"""
ATLAS AI
Meme Coin Logging System

Mirrors logger.py exactly, pointed at separate files, so the meme
coin tier has a fully independent trade/equity history.
"""

from pathlib import Path
from datetime import datetime
import csv


LOG_FOLDER = Path("logs")
LOG_FOLDER.mkdir(exist_ok=True)

LOG_FILE = LOG_FOLDER / "meme_atlas_log.csv"

EQUITY_LOG_FILE = LOG_FOLDER / "meme_equity_log.csv"


def initialise_log():
    """Create the log file and headers if it doesn't exist."""

    if not LOG_FILE.exists():

        with open(LOG_FILE, "w", newline="", encoding="utf-8") as file:

            writer = csv.writer(file)

            writer.writerow([
                "Date", "Time", "Symbol", "Decision",
                "Confidence", "Price", "Message",
            ])


def log_trade(symbol, decision, confidence, price, message=""):
    """Record a paper or trading decision."""

    initialise_log()

    now = datetime.now()

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as file:

        writer = csv.writer(file)

        writer.writerow([
            now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"),
            symbol, decision, confidence, price, message,
        ])


def log_info(message):
    """Record an informational event."""

    initialise_log()

    now = datetime.now()

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as file:

        writer = csv.writer(file)

        writer.writerow([
            now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"),
            "", "", "", "", message,
        ])


def log_error(message):
    """Record an error."""

    initialise_log()

    now = datetime.now()

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as file:

        writer = csv.writer(file)

        writer.writerow([
            now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"),
            "", "ERROR", "", "", message,
        ])


def initialise_equity_log():
    """Create the equity log file and headers if it doesn't exist."""

    if not EQUITY_LOG_FILE.exists():

        with open(EQUITY_LOG_FILE, "w", newline="", encoding="utf-8") as file:

            writer = csv.writer(file)

            writer.writerow([
                "Date", "Time", "Cash", "PositionValue", "TotalEquity",
                "RealisedPnL", "UnrealisedPnL", "TotalPnL",
                "OpenPositions", "TradeCount", "Wins", "Losses",
            ])


def log_equity(equity):
    """Record a snapshot of paper-account equity."""

    initialise_equity_log()

    now = datetime.now()

    with open(EQUITY_LOG_FILE, "a", newline="", encoding="utf-8") as file:

        writer = csv.writer(file)

        writer.writerow([
            now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"),
            equity["cash"], equity["position_value"], equity["total_equity"],
            equity["realised_pnl"], equity["unrealised_pnl"], equity["total_pnl"],
            equity["open_positions"], equity["trade_count"],
            equity["wins"], equity["losses"],
        ])


initialise_log()
initialise_equity_log()
