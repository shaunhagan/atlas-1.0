"""
=========================================
ATLAS AI
Professional Trading Platform
=========================================
"""

from logger import log_info
from scanner import scan_market


def startup():

    print("\n")
    print("=" * 70)
    print("                    ATLAS AI")
    print("=" * 70)
    print("Crypto • Stocks • Forex")
    print("Professional Trading Platform")
    print("=" * 70)

    log_info("Atlas Started")


def shutdown():

    print("\n")

    log_info("Atlas Stopped")

    print("Atlas Shutdown Complete")


def main():

    startup()

    try:

        scan_market()

    except KeyboardInterrupt:

        shutdown()


if __name__ == "__main__":
    main()