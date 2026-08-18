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

## 2026-08-18 (cont.) -- Full sweep: baseline validated, sweep result rejected as overfit

Ran the full staged sweep (30 sweep symbols, friction included, 25% of
the 30-day window held out as test): `ATR_STOP_MULTIPLIER` in
[5,8,10,14,20], `RISK_REWARD_RATIO` in [1.5,2,2.5,3,4],
`MIN_CONFIDENCE` in [55,60,65,70,75,80].

**Baseline (current live config: ATR=10, RR=2.5, min_conf=70) confirmed
on the full 60-symbol volume-ranked set, WITH friction:**
- Full period: 579 trades, 27.1% win rate, +0.777% expectancy
- **Held-out test period: 88 trades, 19.3% win rate, +0.610% expectancy**

This is the first properly validated (out-of-sample, fee-inclusive)
positive result. It appears to be driven mainly by the volume-ranking
symbol-selection fix earlier today, not by any exit-parameter tuning.

**Sweep's nominal "winner" (ATR=20, RR=2.0, min_conf=60): REJECTED.**
Train-period expectancy looked spectacular (+7.095% at one grid point)
but only because trade count collapsed as parameters tightened (759
trades down to 69-97) -- a handful of surviving trades getting lucky,
not real signal. Held-out test period had only **15 trades** (below the
significance bar) and a win rate (20.0%) barely different from
baseline's (19.3%). Textbook overfit, caught by the train/test split
exactly as designed.

**Decision: no config.py change from this sweep.** Current live
parameters (ATR_STOP_MULTIPLIER=10, RISK_REWARD_RATIO=2.5,
MIN_CONFIDENCE=70) remain the best validated choice. Do not re-run this
exact grid search expecting a different conclusion -- the exit-parameter
space around the current values appears to be a fairly flat plateau, not
a space with an easy nearby improvement. Effort from here is better
spent on the signal formula itself (see below) than more exit-parameter
sweeping.

## 2026-08-18 (cont.) -- Signal component ablation

Built `ablate.py`: toggles each scoring component off one at a time
(`SignalEngine.evaluate` gained `use_trend`/`use_rsi`/`use_macd`/
`use_momentum`/`use_volume`/`use_chop_gate` flags, all default True,
live behaviour unchanged) and compares train/test expectancy against
the full-signal baseline. 30 symbols, same train/test split as the
exit-parameter sweep.

**Baseline: 234 train / 38 test trades, test expectancy +1.978%.**

| Removed | Test N | Test Expectancy | Verdict |
|---|---|---|---|
| trend (EMA) | 0 | n/a | Structurally required -- confidence never reaches MIN_CONFIDENCE without it |
| RSI | 33 | -3.197% | Removing it hurts -- keep |
| MACD | 59 | -1.558% | Removing it hurts -- keep |
| momentum (histogram sign) | 39 | **+2.533%** | Removing it *helps*, and N is nearly unchanged (38->39, the cleanest comparison here since trade population barely shifted) |
| volume | 33 | +0.607% | Removing it hurts -- keep |
| chop-gate | 889 | -0.120%, ~1% win rate | Removing it is catastrophic (12x more trades, near-zero win rate) -- absolutely keep |

RSI, MACD, volume, and the chop-gate are all clearly load-bearing --
removing any of them makes out-of-sample results meaningfully worse.
No ambiguity there, no further action needed on those four.

**Momentum (histogram sign, `use_momentum`) is the one open question.**
38-39 trades is still a small sample on its own (same order of
magnitude as the ATR=20 result rejected earlier today) -- running a
confirmatory test on the full 60-symbol set before making any code
change. Check for a following dated entry with that result before
repeating this test.

## What's next (unexplored, in rough priority order)

1. ~~Validate the volume-ranking result properly~~ -- DONE, see
   2026-08-18 (cont.) entry above. Confirmed out-of-sample with friction
   included: +0.610%/trade over 88 held-out trades.
2. ~~Exit-parameter sweep (ATR multiplier / risk:reward / confidence
   threshold)~~ -- DONE, see same entry. No improvement found; current
   live values already appear near-optimal in that parameter space.
3. **Signal formula itself has never been tuned or validated** -- this
   is now the top priority. Only exit parameters have been swept so far.
   The earlier 507-trade backtest found the 70-79 confidence bucket
   outperforming 80-99, suggesting some scoring component may be
   actively unhelpful. Try component ablation: does removing/reweighting
   RSI, MACD, EMA-spread, or the volume score change out-of-sample
   expectancy? Use the same train/test discipline as the exit sweep --
   whatever "wins" must hold up on a held-out period with a meaningful
   trade count (learn from the ATR=20 rejection above).
4. **Multi-timeframe confirmation** -- require 1h trend agreement before
   a 5m entry. Common fix for exactly this kind of "looks fine, doesn't
   hold up" signal problem. Not yet attempted.
5. **A second, non-overlapping historical window.** Everything so far is
   one 30-day period with one train/test split inside it. A real
   validation needs testing across multiple distinct time windows (e.g.
   a different prior month) to rule out this period being unusual.
6. Wider/finer exit-parameter grids only if #3 or #4 change the picture
   enough to be worth revisiting -- not before, given #2's conclusion.
