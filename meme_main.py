"""
=========================================
ATLAS AI
Meme Coin Trading Entry Point
=========================================

Runs independently of main.py (crypto) and stock_main.py (stocks) --
separate process, separate portfolio, separate logs. The high-risk
tier: deliberately more aggressive risk settings, no regime/HTF
filter, Kraken meme coin pairs. Run all three side by side for three
fully independent paper-trading books.
"""

from meme_logger import log_info
from meme_scanner import scan_market


def startup():

    print("\n")
    print("=" * 70)
    print("               ATLAS AI - MEME COINS (HIGH RISK)")
    print("=" * 70)
    print("Kraken meme coin pairs, paper trading")
    print("=" * 70)

    log_info("Atlas Meme Coins Started")


def shutdown():

    print("\n")

    log_info("Atlas Meme Coins Stopped")

    print("Atlas Meme Coins Shutdown Complete")


def main():

    startup()

    try:

        scan_market()

    except KeyboardInterrupt:

        shutdown()


if __name__ == "__main__":
    main()
