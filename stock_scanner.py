"""
ATLAS AI
Stock Market Scanner

Mirrors scanner.py's structure, using stock_exchange/stock_paper_trader/
stock_portfolio/stock_logger for full independence from crypto, plus
market-hours awareness (stocks trade ~6.5h/weekday, unlike crypto's
24/7).

Runs a Bollinger Band + RSI mean-reversion entry, not crypto's EMA/
RSI/MACD trend engine -- STOCK_OPTIMIZATION_LOG.md: five independent
validation attempts found zero edge for the trend engine on stocks
(confirmed live too, 0% win rate over 20 real trades), while mean
reversion showed positive held-out test expectancy in two independent
backtest windows. Not a fully closed case (four regime-filter
hypotheses failed to explain why one window was much stronger than
the other), but meaningfully better-evidenced than an engine already
proven dead. No regime/HTF filter live -- none tested for either
strategy have validated yet; a stock-specific filter should go
through the same train/test discipline before being trusted, not be
assumed to transfer from crypto or added on a hunch.
"""

import time

from config import (
    STOCK_SCAN_INTERVAL,
    SHOW_TOP,
    DAILY_LOSS_LIMIT_PCT,
    BOLLINGER_PERIOD,
    BOLLINGER_STDDEV,
    MEANREV_RSI_OVERSOLD,
)

from stock_exchange import exchange
from indicators import Indicators

import stock_portfolio as portfolio
from stock_logger import log_equity
from risk_guard import check_daily_loss_limit, check_portfolio_heat

from stock_paper_trader import (
    execute as execute_paper_trade,
    check_all_positions,
)


# Fixed confidence assigned to any firing mean-reversion signal --
# unlike the trend engine's point-tally, this entry is a binary
# condition (price at/below the lower band AND RSI confirms oversold),
# so there's no natural graduated score to report. Value only matters
# for display/logging; the entry decision itself doesn't threshold on
# it the way the old MIN_CONFIDENCE gate did.
MEANREV_SIGNAL_CONFIDENCE = 75


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

        rsi = Indicators.rsi(closes)

        atr = Indicators.atr(highs, lows, closes)

        upper, middle, lower = Indicators.bollinger_bands(
            closes, BOLLINGER_PERIOD, BOLLINGER_STDDEV,
        )

        # ----------------------------------------------------
        # Mean-reversion entry: price at/below the lower band AND
        # RSI confirms oversold. Requiring both, not either, matches
        # stock_meanrev_backtest.py exactly -- BB-alone is prone to
        # false signals in trending regimes, RSI confirmation is the
        # standard fix. Long-only, no SELL side (matches the rest of
        # this project -- no shorting anywhere).
        # ----------------------------------------------------

        signal_fired = (
            rsi == rsi
            and lower == lower
            and current_price <= lower
            and rsi < MEANREV_RSI_OVERSOLD
        )

        decision = "BUY" if signal_fired else "HOLD"
        confidence = MEANREV_SIGNAL_CONFIDENCE if signal_fired else 0

        reasons = (
            [f"Price at/below lower Bollinger Band, RSI {rsi:.1f} oversold"]
            if signal_fired else []
        )

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
            "rsi": rsi,
            "bb_upper": upper,
            "bb_middle": middle,
            "bb_lower": lower,
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

        if data["decision"] == "BUY":

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
            f"BB Lower   : {trade['bb_lower']:.6f}"
        )

        print(
            f"BB Middle  : {trade['bb_middle']:.6f}"
        )

        print(
            f"BB Upper   : {trade['bb_upper']:.6f}"
        )

        print(
            f"RSI        : {trade['rsi']:.2f}"
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

    No regime/HTF gate here -- four regime-filter hypotheses were
    tried for the mean-reversion entry (ADX, SPY volatility,
    volatility+trend, trend direction) and none held up
    (STOCK_OPTIMIZATION_LOG.md 2026-08-29/30); a stock-specific
    regime filter should go through the same train/test validation
    before being trusted, not be assumed to transfer or bolted on
    from a hunch. The daily loss circuit breaker and portfolio heat
    gate are asset-agnostic though, so both apply here too -- neither
    gates exits.

    Heat gate added 2026-09-05: validated via portfolio_backtest.py's
    shared-state engine (stock_portfolio_heat_test.py) -- milder
    effect than meme's (stocks span far more diverse sectors, so
    correlated book-wide moves are less pronounced), but directionally
    positive and not harmful (test expectancy +1.150% -> +1.571%).
    """

    daily_ok = check_daily_loss_limit(
        portfolio, "stocks", DAILY_LOSS_LIMIT_PCT
    )

    if not daily_ok:
        print(
            f"\nDaily loss limit reached ({DAILY_LOSS_LIMIT_PCT}%) -- "
            f"new entries paused for the rest of the day, existing "
            f"positions still managed normally."
        )

    heat_ok = check_portfolio_heat(portfolio, exchange, "stocks")

    if not heat_ok:
        print(
            f"\nBook heat too high (most open positions underwater) -- "
            f"new entries paused until it cools off, existing "
            f"positions still managed normally."
        )

    entries_ok = daily_ok and heat_ok

    for trade in results:

        symbol = trade["symbol"]
        decision = trade["decision"]
        confidence = trade["confidence"]
        price = trade["price"]
        atr = trade["atr"]

        if decision == "BUY" and not entries_ok:
            continue

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
