"""
=========================================
ATLAS AI
Stock Trading Entry Point
=========================================

Runs independently of main.py (crypto) -- separate process, separate
portfolio, separate logs. Run both side by side for two fully
independent paper-trading books.
"""

from stock_logger import log_info
from stock_scanner import scan_market


def startup():

    print("\n")
    print("=" * 70)
    print("                 ATLAS AI - STOCKS")
    print("=" * 70)
    print("US Equities (Alpaca, paper trading)")
    print("=" * 70)

    log_info("Atlas Stocks Started")


def shutdown():

    print("\n")

    log_info("Atlas Stocks Stopped")

    print("Atlas Stocks Shutdown Complete")


def main():

    startup()

    try:

        scan_market()

    except KeyboardInterrupt:

        shutdown()


if __name__ == "__main__":
    main()
