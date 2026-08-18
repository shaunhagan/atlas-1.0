# Atlas Optimization Log

Running record of strategy experiments: what's been tried, what worked,
what didn't, and what's next. Read this before starting new work so
effort isn't wasted repeating the same experiment.

**Rules for anyone/anything adding to this log:**
- Append a new dated entry, don't rewrite history.
- Every claim needs a number from `backtest.py`/`optimize.py` behind it,
  ideally out-of-sample (test-period, not train-period).
- If a change looks like a genuine improvement, open a PR with the
  `config.py` change -- never push directly to `master`. The live bot
  runs on a real (if paper) account and a bad parameter has already
  gone out once (see 2026-08-17 entry) before being caught.

---

## 2026-08-15 -- Baseline signal engine

Built the original scanner: EMA20/50 + RSI + MACD confidence scoring,
fixed 2% stop-loss / 5% take-profit, `MAX_OPEN_TRADES=10`.

## 2026-08-16 -- Volume filter + chop gate

Added volume-ratio confirmation and wired up previously-dead
`MIN_EMA_SPREAD_PCT`/`MIN_MACD_HIST_PCT` config as a hard gate against
trading in choppy, low-conviction markets.

## 2026-08-17 -- ATR-based risk management

**Problem found:** live results after `MAX_OPEN_TRADES` 10->30: 14 closed
trades, 7.1% win rate. Breakeven for a 2%/5% (2.5:1) stop/target needs
~28.6% win rate. Structurally losing.

**Fix:** replaced fixed % stop/target with ATR-based adaptive stops,
sized via true risk-per-trade (`RISK_PER_TRADE` config, previously dead).

**Mistake caught and fixed same day:** first attempt used
`ATR_STOP_MULTIPLIER=2.0`-`3.0` (textbook value for same-timeframe ATR
stops). Real 5-minute-candle ATR on these pairs is only ~0.1-0.6% of
price, so 3x produced stops *tighter* than the broken 2% baseline --
would have made things worse. Caught by checking real position SL/TP
distances against live data before letting it run. Corrected to
`ATR_STOP_MULTIPLIER=10.0` (a reasoned estimate from live ATR magnitudes,
not backtested-optimal).

**Result after fix (34 closed trades, overnight run):** win rate 17.6%,
payoff ratio ~4.7:1, breakeven win rate for that ratio is ~17.5% --
landed almost exactly on breakeven. Real improvement, not yet an edge.

## 2026-08-18 -- Backtester built; bigger-sample reality check

Built `backtest.py`: replays the live signal engine + ATR bracket exit
against real historical candles, no waiting on live time.

**507-trade backtest (60 symbols, alphabetically-selected, 30 days):**
overall expectancy **-0.106%/trade**. Confidence score does NOT cleanly
predict quality -- the 70-79 bucket outperformed 80-89 and 90-99. This
is the single most important open finding: the scoring weights in
`signals.py` have never been validated against data, only hand-tuned by
intuition.

**Fix: symbol selection was alphabetical-first-150, not volume-ranked.**
This was arbitrarily excluding high-volume pairs (including major
memecoins -- DOGE/PEPE/SHIB/BONK were sometimes not in scope at all) in
favor of whatever sorted early in the alphabet. Switched
`exchange.get_markets()` to rank by 24h quote volume.

**Dry-run sweep result (5 symbols, small grid) -- important signal:**
on the FULL volume-ranked 60-symbol set, the *current baseline config*
(unchanged) showed **+1.179% expectancy** (528 trades, 30.3% win rate)
vs -0.106% on the old alphabetical set. The volume-ranking fix alone may
be a bigger lever than any exit-parameter tuning done so far.

Also caught real overfitting in the same dry run: the "winning" config
from the tiny 5-symbol sweep actually performed *worse*
(+0.538% vs +1.179%) when confirmed against the full 60-symbol set. This
is why `optimize.py` always re-confirms against a larger set before
trusting a sweep result, and now also splits into train/test periods.

**Added same day:**
- `TRADING_FRICTION_PCT` (fee + slippage, ~0.15%/side) applied to both
  live paper trading and the backtester -- prior expectancy numbers above
  (except the +1.179% dry-run figure, which predates this) did NOT
  include this cost.
- Train/test split in `optimize.py` (last 25% of the window held out from
  tuning) to guard against the overfitting pattern just observed.

**In progress as of this entry:** full sweep (30 sweep symbols, 60-symbol
confirmation, friction included, train/test split) running in the
background. Results TBD -- check for a later dated entry before
re-running the same sweep.

## What's next (unexplored, in rough priority order)

1. **Validate the volume-ranking result properly** -- confirm the
   +1.179% baseline figure holds up with friction included and on the
   held-out test period specifically, not just the dry run's full-period
   number.
2. **Signal formula itself has never been tuned or validated**, only its
   exit parameters. The 70-79-outperforms-90-99 confidence finding above
   suggests some scoring component may be actively unhelpful. Try
   component ablation: does removing/reweighting RSI, MACD, or the volume
   score change out-of-sample expectancy?
3. **Multi-timeframe confirmation** -- require 1h trend agreement before
   a 5m entry. Common fix for exactly this kind of "looks fine, doesn't
   hold up" signal problem. Not yet attempted.
4. **Wider parameter grids / finer search** once the coordinate-descent
   sweep's rough optimum is known, to check it's not a local optimum.
5. Nothing here has been tested on a second, non-overlapping historical
   period beyond the one 30-day/train-test split. A real validation
   would test across multiple distinct time windows.
