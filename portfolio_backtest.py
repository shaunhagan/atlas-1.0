"""
=========================================
ATLAS AI
Shared-State Portfolio Backtester
=========================================

Every backtester so far (backtest.py, stock_backtest.py,
meme_backtest.py, stock_meanrev_backtest.py) simulates each symbol
completely independently -- explicitly documented as a simplification
("no shared-capital / MAX_OPEN_TRADES contention is simulated"). That
makes it impossible to test anything about the PORTFOLIO as a whole,
like whether too many open positions are correlated/moving together --
exactly the failure mode behind meme's 2026-08-28/30 drawdown (16 of
18 traded coins net negative at once, a position-count cap gave zero
protection against it since it isn't designed to).

This engine runs all symbols through ONE synchronized clock with
shared portfolio state (open positions, MAX_OPEN_TRADES contention,
optional "book heat" gate), so portfolio-level ideas can actually be
backtested rather than assumed. Generic over the signal logic and
data source so it works for both meme (trend engine) and stocks
(mean reversion) without duplicating the engine.
"""

from collections import defaultdict


def run_portfolio_backtest(
    symbols,
    candle_cache,
    signal_fn,
    lookback,
    max_open_trades,
    atr_stop_multiplier,
    risk_reward_ratio,
    friction_pct,
    use_heat_gate=False,
    min_positions_for_heat=4,
    loss_fraction_threshold=0.6,
    verbose=True,
):
    """
    signal_fn(closes, highs, lows, volumes) -> (decision, confidence)
    where decision is "BUY" or "HOLD"/"SELL" and volumes may be None
    for strategies that don't use it (mean reversion).

    Returns the list of closed trades (same shape as the per-symbol
    backtesters: symbol/pnl_pct/reason/confidence/entry_ts) plus the
    running equity curve as a list of (ts, num_open, num_underwater).
    """

    # Index each symbol's candles by timestamp for O(1) lookup, and
    # by list position for trailing-window slicing.
    by_ts = {}
    ts_index = {}

    for symbol in symbols:

        candles = candle_cache.get(symbol) or []

        if len(candles) < lookback + 10:
            continue

        by_ts[symbol] = {candle[0]: candle for candle in candles}
        ts_index[symbol] = {candle[0]: i for i, candle in enumerate(candles)}

    if not by_ts:
        return [], []

    all_timestamps = sorted(set().union(*(by_ts[s].keys() for s in by_ts)))

    open_positions = {}
    trades = []
    heat_history = []

    for step, ts in enumerate(all_timestamps):

        # ------------------------------------------------
        # 1. Check every open position for SL/TP at this ts
        # ------------------------------------------------

        for symbol in list(open_positions.keys()):

            candle = by_ts.get(symbol, {}).get(ts)

            if candle is None:
                continue

            position = open_positions[symbol]

            high, low = candle[2], candle[3]

            if low <= position["stop_loss"]:

                exit_fill = position["stop_loss"] * (1 - friction_pct)

                trades.append({
                    "symbol": symbol,
                    "pnl_pct": (exit_fill - position["entry_price"]) / position["entry_price"] * 100,
                    "reason": "STOP LOSS",
                    "confidence": position["confidence"],
                    "entry_ts": position["entry_ts"],
                })

                del open_positions[symbol]

            elif high >= position["take_profit"]:

                exit_fill = position["take_profit"] * (1 - friction_pct)

                trades.append({
                    "symbol": symbol,
                    "pnl_pct": (exit_fill - position["entry_price"]) / position["entry_price"] * 100,
                    "reason": "TAKE PROFIT",
                    "confidence": position["confidence"],
                    "entry_ts": position["entry_ts"],
                })

                del open_positions[symbol]

        # ------------------------------------------------
        # 2. Book-heat gate -- what fraction of currently open
        #    positions are underwater right now, using latest
        #    available close for each.
        # ------------------------------------------------

        entries_allowed = True

        if use_heat_gate and len(open_positions) >= min_positions_for_heat:

            underwater = 0

            for symbol, position in open_positions.items():

                candle = by_ts.get(symbol, {}).get(ts)
                current_close = candle[4] if candle is not None else position["entry_price"]

                if current_close < position["entry_price"]:
                    underwater += 1

            fraction_underwater = underwater / len(open_positions)

            heat_history.append((ts, len(open_positions), underwater))

            if fraction_underwater >= loss_fraction_threshold:
                entries_allowed = False

        # ------------------------------------------------
        # 3. Look for new entries (only symbols with a candle at
        #    this ts, not already held, room in the book)
        # ------------------------------------------------

        if entries_allowed and len(open_positions) < max_open_trades:

            for symbol in by_ts:

                if len(open_positions) >= max_open_trades:
                    break

                if symbol in open_positions:
                    continue

                index = ts_index[symbol].get(ts)

                if index is None or index < lookback:
                    continue

                candles = candle_cache[symbol]
                window = candles[index - lookback:index]

                closes = [c[4] for c in window]
                highs = [c[2] for c in window]
                lows = [c[3] for c in window]
                volumes = [c[5] for c in window]

                try:
                    decision, confidence = signal_fn(closes, highs, lows, volumes)
                except Exception:
                    continue

                if decision != "BUY":
                    continue

                price = closes[-1]
                atr = _atr(highs, lows, closes)

                if atr is None or atr != atr or atr <= 0:
                    continue

                fill_price = price * (1 + friction_pct)
                stop_distance = atr_stop_multiplier * atr
                stop_loss = fill_price - stop_distance

                if stop_loss <= 0:
                    continue

                open_positions[symbol] = {
                    "entry_price": fill_price,
                    "stop_loss": stop_loss,
                    "take_profit": fill_price + (risk_reward_ratio * stop_distance),
                    "confidence": confidence,
                    "entry_ts": ts,
                }

        if verbose and step % 2000 == 0 and step > 0:
            print(f"  ...{step}/{len(all_timestamps)} timesteps, {len(trades)} trades closed so far")

    return trades, heat_history


def _atr(highs, lows, closes, period=14):
    """Lightweight ATR without a pandas round-trip -- this runs inside
    the hottest loop in the whole backtester (every symbol, every
    timestep), so avoiding Series construction here matters."""

    if len(highs) < period + 1:
        return None

    true_ranges = []

    for i in range(-period, 0):

        high, low = highs[i], lows[i]
        prev_close = closes[i - 1]

        true_ranges.append(max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        ))

    return sum(true_ranges) / len(true_ranges)
