"""
ATLAS AI
Stock Market Scanner

Mirrors scanner.py's structure, using stock_exchange/stock_paper_trader/
stock_portfolio/stock_logger for full independence from crypto, plus
market-hours awareness (stocks trade ~6.5h/weekday, unlike crypto's
24/7). No regime/HTF filter is applied yet -- those were validated
specifically against BTC and haven't been tested for stocks at all;
starting with the plain signal engine and researching a stock-specific
filter the same disciplined way, rather than assuming crypto's
transfers over.
"""

import time

from config import (
    STOCK_SCAN_INTERVAL,
    MIN_CONFIDENCE,
    SHOW_TOP,
)

from stock_exchange import exchange
from indicators import Indicators
from signals import SignalEngine

import stock_portfolio as portfolio
from stock_logger import log_equity

from stock_paper_trader import (
    execute as execute_paper_trade,
    check_all_positions,
)


# ============================================================
# MARKET HOURS
# ============================================================

def is_market_open():
    """Ask Alpaca directly rather than hand-rolling timezone/holiday
    logic -- handles weekends and market holidays correctly."""

    try:

        clock = exchange.trading_client.get_clock()

        return clock.is_open, clock.next_open

    except Exception as error:

        print(f"Market clock check error (assuming closed): {error}")

        return False, None


def wait_for_market_open(next_open):
    """Sleep in short increments (not one long blocking sleep) so a
    KeyboardInterrupt stays responsive."""

    print()
    print(
        f"Market closed. Next open: {next_open}. "
        f"Checking again every 5 minutes..."
    )

    while True:

        time.sleep(300)

        open_now, _ = is_market_open()

        if open_now:

            print()
            print("Market is now open.")

            return


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

        closes = [
            float(candle[4])
            for candle in candles
        ]

        volumes = [
            float(candle[5])
            for candle in candles
        ]

        highs = [
            float(candle[2])
            for candle in candles
        ]

        lows = [
            float(candle[3])
            for candle in candles
        ]

        # ----------------------------------------------------
        # Indicators
        # ----------------------------------------------------

        ema_fast = Indicators.ema_fast(closes)
        ema_slow = Indicators.ema_slow(closes)

        rsi = Indicators.rsi(closes)

        macd, signal, histogram = Indicators.macd(closes)

        volume_ratio = Indicators.volume_ratio(volumes)

        atr = Indicators.atr(highs, lows, closes)

        # ----------------------------------------------------
        # Signal Engine
        # ----------------------------------------------------

        result = SignalEngine.evaluate(
            current_price,
            ema_fast,
            ema_slow,
            rsi,
            macd,
            signal,
            histogram,
            volume_ratio,
        )

        decision = result["decision"]
        confidence = result["confidence"]
        reasons = result["reasons"]

        return {
            "symbol": symbol,
            "decision": decision,
            "confidence": confidence,
            "reasons": reasons,
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

        print(
            f"Error analysing {symbol}: {error}"
        )

        return None


# ============================================================
# GET MARKETS
# ============================================================

def get_symbols():
    """Load available markets."""

    print("\nLoading Alpaca tradable equities...\n")

    symbols = exchange.get_markets()

    print(
        f"Loaded {len(symbols)} equity symbols.\n"
    )

    return symbols


# ============================================================
# SCAN ALL MARKETS
# ============================================================

def scan_once():
    """Perform one complete market scan."""

    symbols = get_symbols()

    results = []

    print("Scanning market...\n")

    for symbol in symbols:

        data = analyse_market(symbol)

        if data is None:
            continue

        if data["confidence"] >= MIN_CONFIDENCE:

            results.append(data)

    results.sort(
        key=lambda item: item["confidence"],
        reverse=True,
    )

    return results


# ============================================================
# DISPLAY RESULTS
# ============================================================

def print_results(results):
    """Display the strongest opportunities."""

    print()
    print("=" * 70)
    print("                      ATLAS AI - STOCKS")
    print("=" * 70)

    if not results:

        print()
        print("No high-confidence opportunities found.")
        print()

        return

    print()
    print(
        f"Top {min(SHOW_TOP, len(results))} Opportunities"
    )
    print()

    for index, trade in enumerate(
        results[:SHOW_TOP],
        start=1,
    ):

        print(
            f"{index}. {trade['symbol']} "
            f"| {trade['decision']} "
            f"| {trade['confidence']}%"
        )

        print("-" * 50)

        print(
            f"Price      : {trade['price']:.6f}"
        )

        print(
            f"EMA20      : {trade['ema_fast']:.6f}"
        )

        print(
            f"EMA50      : {trade['ema_slow']:.6f}"
        )

        print(
            f"RSI        : {trade['rsi']:.2f}"
        )

        print(
            f"MACD       : {trade['macd']:.8f}"
        )

        print(
            f"Signal     : {trade['signal']:.8f}"
        )

        print(
            f"Histogram  : {trade['histogram']:.8f}"
        )

        print(
            f"Volume     : x{trade['volume_ratio']:.2f}"
        )

        print(
            f"ATR        : {trade['atr']:.8f}"
        )

        if trade["reasons"]:

            print()
            print("Reasons:")

            for reason in trade["reasons"]:

                print(
                    f"  - {reason}"
                )

        print()


# ============================================================
# SUMMARY
# ============================================================

def display_summary(results):
    """Display signal counts."""

    buys = sum(
        1
        for item in results
        if item["decision"] == "BUY"
    )

    holds = sum(
        1
        for item in results
        if item["decision"] == "HOLD"
    )

    sells = sum(
        1
        for item in results
        if item["decision"] == "SELL"
    )

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
    Send qualifying signals to the paper trader.

    No regime/HTF gate here -- crypto's volatility filter was
    validated specifically against BTC and hasn't been tested for
    stocks at all. Starting with the plain signal engine; a
    stock-specific regime filter (if warranted) should go through the
    same train/test validation crypto's did before being trusted,
    not be assumed to transfer.
    """

    for trade in results:

        symbol = trade["symbol"]
        decision = trade["decision"]
        confidence = trade["confidence"]
        price = trade["price"]
        atr = trade["atr"]

        execute_paper_trade(
            symbol,
            decision,
            confidence,
            price,
            atr,
        )


# ============================================================
# AUTOMATIC POSITION EXIT CHECK
# ============================================================

def check_paper_positions():
    """
    Check every open paper position for
    stop-loss or take-profit.
    """

    try:

        closed_count = check_all_positions()

        if closed_count > 0:

            print()
            print(
                f"Automatic exits triggered: "
                f"{closed_count}"
            )

    except Exception as error:

        print()
        print("Paper Exit Check Error")
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
            f"(Cash {equity['cash']:.2f} + "
            f"Positions {equity['position_value']:.2f}) "
            f"| Total P&L: {equity['total_pnl']:+.2f} "
            f"| Open: {equity['open_positions']}"
        )

    except Exception as error:

        print()
        print("Equity Snapshot Error")
        print(error)


# ============================================================
# MAIN SCANNER LOOP
# ============================================================

def scan_market():
    """Continuously scan the market during trading hours."""

    while True:

        try:

            # ------------------------------------------------
            # Market hours check -- positions still get managed
            # while closed (overnight gaps can still hit SL/TP
            # once the market reopens), just no new scanning.
            # ------------------------------------------------

            open_now, next_open = is_market_open()

            if not open_now:

                check_paper_positions()

                wait_for_market_open(next_open)

                continue

            # ------------------------------------------------
            # Check existing positions BEFORE new signals
            # ------------------------------------------------

            check_paper_positions()

            # ------------------------------------------------
            # Scan markets
            # ------------------------------------------------

            results = scan_once()

            # ------------------------------------------------
            # Display results
            # ------------------------------------------------

            print_results(results)

            display_summary(results)

            # ------------------------------------------------
            # Execute new BUY / SELL signals
            # ------------------------------------------------

            execute_paper_trades(results)

            # ------------------------------------------------
            # Check again after new trades
            # ------------------------------------------------

            check_paper_positions()

            # ------------------------------------------------
            # Record equity snapshot for this cycle
            # ------------------------------------------------

            record_equity_snapshot()

            # ------------------------------------------------
            # Wait for next scan
            # ------------------------------------------------

            print()
            print(
                f"Next scan in "
                f"{STOCK_SCAN_INTERVAL} seconds..."
            )

            print("=" * 70)

            time.sleep(STOCK_SCAN_INTERVAL)

        except KeyboardInterrupt:

            print()
            print("Atlas Stocks stopped by user.")

            break

        except Exception as error:

            print()
            print("Scanner Error")
            print(error)

            print()
            print(
                "Retrying in 10 seconds..."
            )

            time.sleep(10)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    scan_market()
