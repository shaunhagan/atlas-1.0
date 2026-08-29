"""
=========================================
ATLAS AI
Stock Mean-Reversion Backtester (research)
=========================================

Five independent validation attempts on stocks (raw crypto-transplanted
config, exit-parameter sweep, signal ablation, momentum toggle, and a
corrected liquid symbol universe) all found the EMA/RSI/MACD
trend-following engine has no validated edge there
(STOCK_OPTIMIZATION_LOG.md). That combo is a momentum/trend strategy,
and momentum strategies are widely documented to struggle specifically
in efficiently-priced large-cap equities (heavy arbitrage, high
turnover/transaction-cost drag) while mean-reversion has real
intraday-timeframe evidence. This tests a structurally different
entry signal -- Bollinger Bands + RSI extremes -- rather than another
retune of an engine already shown dead.

Reuses stock_backtest.py's fetch_history/exchange/caching directly
(same data, same cache folder) and keeps the same ATR-based bracket
exit and position mechanics as everywhere else in this project, so
the ONLY thing that differs from the trend-engine backtest is the
entry signal -- an apples-to-apples comparison, not a confound of
also changing risk management at the same time.

Long-only, matching the rest of this project (no shorting anywhere).
"""

from tabulate import tabulate

import stock_backtest
from stock_backtest import exchange, fetch_history, SYMBOL_LIMIT, BACKTEST_DAYS
from indicators import Indicators
from config import (
    STOCK_ATR_STOP_MULTIPLIER,
    STOCK_RISK_REWARD_RATIO,
    STOCK_TRADING_FRICTION_PCT,
    STOCK_CANDLE_LIMIT,
    BOLLINGER_PERIOD,
    BOLLINGER_STDDEV,
    MEANREV_RSI_OVERSOLD,
    ADX_PERIOD,
)


def simulate_symbol(
    symbol,
    candles,
    atr_stop_multiplier=STOCK_ATR_STOP_MULTIPLIER,
    risk_reward_ratio=STOCK_RISK_REWARD_RATIO,
    friction_pct=STOCK_TRADING_FRICTION_PCT,
    rsi_oversold=MEANREV_RSI_OVERSOLD,
    bollinger_period=BOLLINGER_PERIOD,
    bollinger_stddev=BOLLINGER_STDDEV,
    max_adx=None,
    adx_period=ADX_PERIOD,
    regime_ok_fn=None,
):
    """Same ATR bracket exit mechanics as stock_backtest.simulate_symbol
    -- only the entry condition differs (BB lower band + RSI oversold
    instead of the EMA/RSI/MACD trend engine).

    max_adx: optional regime gate -- skip entries when ADX is above
    this (i.e. the market is trending, not ranging). None = no gate,
    matching the original ungated research result.

    regime_ok_fn: optional external, timestamp-keyed gate (e.g. a SPY
    volatility filter from regime_filter_test.build_regime_filters) --
    same interface backtest.py/stock_backtest.py already use, so it's
    a drop-in for testing market-wide (not per-symbol) regime signals."""

    lookback = max(STOCK_CANDLE_LIMIT, bollinger_period, adx_period * 3)

    trades = []

    in_position = False
    entry_price = None
    stop_loss = None
    take_profit = None
    entry_ts = None

    for i in range(lookback, len(candles)):

        if in_position:

            candle = candles[i]

            high = candle[2]
            low = candle[3]

            if low <= stop_loss:

                exit_fill = stop_loss * (1 - friction_pct)

                trades.append({
                    "symbol": symbol,
                    "pnl_pct": (exit_fill - entry_price) / entry_price * 100,
                    "reason": "STOP LOSS",
                    "confidence": None,
                    "entry_ts": entry_ts,
                })

                in_position = False

            elif high >= take_profit:

                exit_fill = take_profit * (1 - friction_pct)

                trades.append({
                    "symbol": symbol,
                    "pnl_pct": (exit_fill - entry_price) / entry_price * 100,
                    "reason": "TAKE PROFIT",
                    "confidence": None,
                    "entry_ts": entry_ts,
                })

                in_position = False

            continue

        window = candles[i - lookback:i]

        closes = [candle[4] for candle in window]
        highs = [candle[2] for candle in window]
        lows = [candle[3] for candle in window]

        price = closes[-1]

        try:

            rsi = Indicators.rsi(closes)
            atr = Indicators.atr(highs, lows, closes)
            upper, middle, lower = Indicators.bollinger_bands(
                closes, bollinger_period, bollinger_stddev,
            )

        except Exception:
            continue

        if atr is None or atr != atr or atr <= 0:
            continue

        if rsi is None or rsi != rsi:
            continue

        if lower is None or lower != lower:
            continue

        # Entry: price at/below the lower band AND RSI confirms
        # oversold -- requiring both, not either, is deliberate (the
        # research consistently flags BB-alone as prone to false
        # signals in trending regimes; RSI confirmation is the
        # standard fix).
        if not (price <= lower and rsi < rsi_oversold):
            continue

        if max_adx is not None:

            try:
                adx = Indicators.adx(highs, lows, closes, adx_period)
            except Exception:
                continue

            if adx is None or adx != adx or adx > max_adx:
                continue

        if regime_ok_fn is not None and not regime_ok_fn(candles[i][0]):
            continue

        stop_distance = atr_stop_multiplier * atr

        fill_price = price * (1 + friction_pct)

        candidate_stop = fill_price - stop_distance

        if candidate_stop <= 0:
            continue

        entry_price = fill_price
        stop_loss = candidate_stop
        take_profit = fill_price + (risk_reward_ratio * stop_distance)
        entry_ts = candles[i][0]

        in_position = True

    return trades


def run_backtest(
    symbol_limit=SYMBOL_LIMIT,
    days=BACKTEST_DAYS,
    symbols=None,
    candle_cache=None,
    verbose=True,
    **simulate_kwargs,
):

    if symbols is None:
        symbols = exchange.get_markets()[:symbol_limit]

    if verbose:
        print(f"Mean-reversion backtesting {len(symbols)} symbols over {days} days...\n")

    all_trades = []

    for index, symbol in enumerate(symbols, start=1):

        try:

            if candle_cache is not None and symbol in candle_cache:
                candles = candle_cache[symbol]
            else:
                candles = fetch_history(symbol, days)
                if candle_cache is not None:
                    candle_cache[symbol] = candles

            if len(candles) < STOCK_CANDLE_LIMIT + 10:
                if verbose:
                    print(f"[{index}/{len(symbols)}] {symbol}: skipped (not enough history)")
                continue

            trades = simulate_symbol(symbol, candles, **simulate_kwargs)

            all_trades.extend(trades)

            if verbose:
                print(f"[{index}/{len(symbols)}] {symbol}: {len(candles)} candles, {len(trades)} trades")

        except Exception as error:

            if verbose:
                print(f"[{index}/{len(symbols)}] {symbol}: ERROR {error}")

    return all_trades


def print_backtest_report(trades):

    print()
    print("=" * 70)
    print("     ATLAS AI STOCKS - MEAN REVERSION BACKTEST REPORT")
    print("=" * 70)

    if not trades:
        print("\nNo trades were generated.")
        return

    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]

    win_rate = len(wins) / len(trades) * 100
    avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0.0
    avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0.0
    expectancy = sum(t["pnl_pct"] for t in trades) / len(trades)

    print(f"\nTotal Trades     : {len(trades)}")
    print(f"Win Rate         : {win_rate:.1f}% ({len(wins)}W / {len(losses)}L)")
    print(f"Average Win      : {avg_win:+.2f}%")
    print(f"Average Loss     : {avg_loss:+.2f}%")
    print(f"Expectancy/Trade : {expectancy:+.3f}%")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    trades = run_backtest()
    print_backtest_report(trades)
