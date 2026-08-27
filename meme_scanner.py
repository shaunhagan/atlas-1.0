"""
ATLAS AI
Meme Coin Market Scanner

Mirrors scanner.py's structure, using meme_exchange (Kraken)/
meme_paper_trader/meme_portfolio/meme_logger for full independence
from both the crypto and stock books. Deliberately no regime/HTF
filter here -- this tier is meant to be the fast, aggressive,
unfiltered one by design. The one safety net kept is the (much
higher-threshold) daily loss circuit breaker, same asset-agnostic
risk_guard.py the other two books use.
"""

import time

from config import (
    MEME_SCAN_INTERVAL,
    MEME_MIN_CONFIDENCE,
    SHOW_TOP,
    MEME_DAILY_LOSS_LIMIT_PCT,
)

from meme_exchange import exchange
from indicators import Indicators
from signals import SignalEngine

import meme_portfolio as portfolio
from meme_logger import log_equity
from risk_guard import check_daily_loss_limit

from meme_paper_trader import (
    execute as execute_paper_trade,
    check_all_positions,
)


# ============================================================
# ANALYSE ONE MARKET
# ============================================================

def analyse_market(symbol):
    """Analyse one market and return its trading signal."""

    try:

        ticker = exchange.get_ticker(symbol)
        candles = exchange.get_candles(symbol)

        if not candles or len(candles) < 60:
            return None

        current_price = ticker.get("last")

        if current_price is None:
            return None

        current_price = float(current_price)

        if current_price <= 0:
            return None

        latest = candles[-1]

        open_price = float(latest[1])
        high_price = float(latest[2])
        low_price = float(latest[3])
        close_price = float(latest[4])

        closes = [float(candle[4]) for candle in candles]
        volumes = [float(candle[5]) for candle in candles]
        highs = [float(candle[2]) for candle in candles]
        lows = [float(candle[3]) for candle in candles]

        ema_fast = Indicators.ema_fast(closes)
        ema_slow = Indicators.ema_slow(closes)
        rsi = Indicators.rsi(closes)
        macd, signal, histogram = Indicators.macd(closes)
        volume_ratio = Indicators.volume_ratio(volumes)
        atr = Indicators.atr(highs, lows, closes)

        result = SignalEngine.evaluate(
            current_price, ema_fast, ema_slow, rsi,
            macd, signal, histogram, volume_ratio,
            min_confidence=MEME_MIN_CONFIDENCE,
        )

        return {
            "symbol": symbol,
            "decision": result["decision"],
            "confidence": result["confidence"],
            "reasons": result["reasons"],
            "price": current_price,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "rsi": rsi,
            "macd": macd,
            "signal": signal,
            "histogram": histogram,
            "volume_ratio": volume_ratio,
            "atr": atr,
        }

    except Exception as error:

        print(f"Error analysing {symbol}: {error}")

        return None


# ============================================================
# GET MARKETS
# ============================================================

def get_symbols():
    """Load available meme coin markets."""

    print("\nLoading Kraken meme coin markets...\n")

    symbols = exchange.get_markets()

    print(f"Loaded {len(symbols)} meme coin markets.\n")

    return symbols


# ============================================================
# SCAN ALL MARKETS
# ============================================================

def scan_once():
    """Perform one complete market scan."""

    symbols = get_symbols()

    results = []

    print("Scanning meme coin market...\n")

    for symbol in symbols:

        data = analyse_market(symbol)

        if data is None:
            continue

        if data["confidence"] >= MEME_MIN_CONFIDENCE:
            results.append(data)

    results.sort(key=lambda item: item["confidence"], reverse=True)

    return results


# ============================================================
# DISPLAY RESULTS
# ============================================================

def print_results(results):
    """Display the strongest opportunities."""

    print()
    print("=" * 70)
    print("                    ATLAS AI - MEME COINS")
    print("=" * 70)

    if not results:
        print("\nNo high-confidence opportunities found.\n")
        return

    print(f"\nTop {min(SHOW_TOP, len(results))} Opportunities\n")

    for index, trade in enumerate(results[:SHOW_TOP], start=1):

        print(f"{index}. {trade['symbol']} | {trade['decision']} | {trade['confidence']}%")
        print("-" * 50)
        print(f"Price      : {trade['price']:.8f}")
        print(f"EMA20      : {trade['ema_fast']:.8f}")
        print(f"EMA50      : {trade['ema_slow']:.8f}")
        print(f"RSI        : {trade['rsi']:.2f}")
        print(f"Volume     : x{trade['volume_ratio']:.2f}")
        print(f"ATR        : {trade['atr']:.8f}")

        if trade["reasons"]:
            print("\nReasons:")
            for reason in trade["reasons"]:
                print(f"  - {reason}")

        print()


# ============================================================
# SUMMARY
# ============================================================

def display_summary(results):
    """Display signal counts."""

    buys = sum(1 for item in results if item["decision"] == "BUY")
    holds = sum(1 for item in results if item["decision"] == "HOLD")
    sells = sum(1 for item in results if item["decision"] == "SELL")

    print("Market Summary")
    print("-" * 30)
    print(f"BUY Signals : {buys}")
    print(f"HOLD Signals: {holds}")
    print(f"SELL Signals: {sells}")


# ============================================================
# PAPER TRADING
# ============================================================

def execute_paper_trades(results):
    """
    Send qualifying signals to the paper trader. No regime/HTF gate
    by design (this tier is meant to be fast/aggressive/unfiltered) --
    the daily loss circuit breaker is the one safety net, at a much
    higher threshold than the safe tier's.
    """

    daily_ok = check_daily_loss_limit(portfolio, "meme", MEME_DAILY_LOSS_LIMIT_PCT)

    if not daily_ok:
        print(
            f"\nDaily loss limit reached ({MEME_DAILY_LOSS_LIMIT_PCT}%) -- "
            f"new entries paused for the rest of the day, existing "
            f"positions still managed normally."
        )

    for trade in results:

        symbol = trade["symbol"]
        decision = trade["decision"]
        confidence = trade["confidence"]
        price = trade["price"]
        atr = trade["atr"]

        if decision == "BUY" and not daily_ok:
            continue

        execute_paper_trade(symbol, decision, confidence, price, atr)


# ============================================================
# AUTOMATIC POSITION EXIT CHECK
# ============================================================

def check_paper_positions():
    """Check every open paper position for stop-loss or take-profit."""

    try:

        closed_count = check_all_positions()

        if closed_count > 0:
            print(f"\nAutomatic exits triggered: {closed_count}")

    except Exception as error:

        print("\nPaper Exit Check Error")
        print(error)


# ============================================================
# EQUITY SNAPSHOT
# ============================================================

def record_equity_snapshot():
    """Snapshot current paper equity and append it to the equity log."""

    try:

        equity = portfolio.get_equity()

        log_equity(equity)

        print()
        print(
            f"Equity: {equity['total_equity']:.2f} "
            f"(Cash {equity['cash']:.2f} + Positions {equity['position_value']:.2f}) "
            f"| Total P&L: {equity['total_pnl']:+.2f} "
            f"| Open: {equity['open_positions']}"
        )

    except Exception as error:

        print("\nEquity Snapshot Error")
        print(error)


# ============================================================
# MAIN SCANNER LOOP
# ============================================================

def scan_market():
    """Continuously scan the meme coin market."""

    while True:

        try:

            check_paper_positions()

            results = scan_once()

            print_results(results)
            display_summary(results)

            execute_paper_trades(results)

            check_paper_positions()

            record_equity_snapshot()

            print(f"\nNext scan in {MEME_SCAN_INTERVAL} seconds...")
            print("=" * 70)

            time.sleep(MEME_SCAN_INTERVAL)

        except KeyboardInterrupt:

            print("\nAtlas Meme Coins stopped by user.")
            break

        except Exception as error:

            print("\nScanner Error")
            print(error)
            print("\nRetrying in 10 seconds...")

            time.sleep(10)


if __name__ == "__main__":
    scan_market()
