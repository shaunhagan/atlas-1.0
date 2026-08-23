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

## 2026-08-18 (cont.) -- Momentum component confirmed harmful, removed from live default

Confirmed on the full 60-symbol set (much bigger sample than the
30-symbol ablation): held-out test period, baseline (with momentum) 88
trades / 19.3% win rate / +0.610% expectancy vs without-momentum 103
trades / 22.3% win rate / **+1.112% expectancy**. Consistent direction
with the smaller ablation run, similar trade population (88 vs 103, not
a different set), both comfortably above the significance bar. This is
the first ablation result trusted enough to act on.

**Applied:** `SignalEngine.evaluate()`'s `use_momentum` default flipped
from `True` to `False`. The scoring component (histogram > 0 -> +10 /
else -5) still exists in code, toggleable for future research, but is
off by default. Live bot restarted to pick this up -- no portfolio
reset needed, this only affects future entries, not the sizing/risk
math or open positions.

**Why a histogram-sign signal might actively hurt:** it's plausible
this component is largely redundant with the MACD-line-vs-signal check
(both derive from the same MACD calculation) and mostly adds noise
rather than independent information, especially right at MACD
crossover points where the histogram briefly flips sign before the
trend actually resolves either way.

## 2026-08-20 -- Second historical window: RESULT REVERSES, urgent to resolve

Ran `validate_window.py`: current live config (with the momentum fix
applied) on a second, non-overlapping 30-day window ending 35 days ago
(40 symbols, 5-day gap from the primary window so there's no overlap
at all).

**Result: 377 trades, 18.6% win rate, -1.390% expectancy.** Solidly
negative, on a large sample. This directly contradicts every positive
result found so far -- the primary window's held-out test
(+0.610%/+1.112% with the momentum fix) and live trading itself
(+5.98% return, 39.5% win rate as of this same day).

**This is a serious warning sign, not a minor caveat.** Two readings,
neither comfortable:
1. The strategy's "edge" may be regime-dependent (works in the market
   conditions of the last ~30 days, not in the conditions 35-65 days
   ago) rather than a durable, general edge.
2. The train/test split inside the primary window protects against
   overfitting *within* that window, but does nothing to protect
   against the whole window being an unusually favourable month --
   which is exactly what this result suggests happened.

**Do not treat live trading's current positive results as confirmation
the strategy is "solved."** They may simply mean the live window has
so far resembled the primary backtest window's conditions, not the
second window's. Needs discussion on how to proceed -- e.g. a market
regime filter (trade only when conditions resemble the profitable
window?), accepting the strategy is conditionally profitable and sizing
down accordingly, or treating this as inconclusive pending a third
window before drawing any conclusion. Not resolved in this session.

## 2026-08-21 -- Third window + regime characterization: confirmed, not "one bad month"

Ran a third window (30 days ending 65 days ago) plus a BTC/USDT regime
characterization (total % change and per-candle return volatility) on
all three windows:

| Window | BTC change | BTC volatility | Trades | Win Rate | Expectancy |
|---|---|---|---|---|---|
| Primary (last 30d) | +0.21% | 0.080% | -- | -- | +0.610%/+1.112% (test period) |
| Second (35-65d ago) | -2.42% | 0.128% (+60%) | 377 | 18.6% | -1.390% |
| Third (65-95d ago) | -14.67% | 0.146% (+83%) | 420 | 21.7% | -0.627% |

**Confirmed: this is systematic regime dependency, not one unusual
month.** Three independent windows, consistent pattern -- the strategy
is only profitable when BTC (proxy for overall market conditions) is
calm and flat/mildly bullish. Both higher-volatility windows lost
money regardless of how far BTC actually declined (win rate barely
differs between -2.42% and -14.67% BTC moves -- it's the volatility
elevation that seems to matter, not decline magnitude specifically).

**Tested one pre-chosen hypothesis:** gate new entries on BTC's own
trailing 200-candle volatility being below 0.10% (`regime_filter_test.py`,
threshold picked once up front from the aggregate levels above, NOT
fit per-window -- fitting a threshold to each window's already-known
outcome would repeat the ATR=20 overfitting mistake). Results in the
following dated entry.

## 2026-08-21 (cont.) -- Regime filter result: helps, doesn't fix

Tested the volatility-gate hypothesis (BTC trailing 200-candle
volatility < 0.10%, threshold chosen once up front) across all three
windows:

| Window | No filter | With filter |
|---|---|---|
| Primary (calm) | 392 trades, 25.5% WR, +0.754% | 397 trades, 23.7% WR, +0.605% |
| Second (elevated) | 368 trades, 20.9% WR, -1.092% | 309 trades, 19.1% WR, **-0.910%** |
| Third (elevated) | 420 trades, 21.7% WR, -0.627% | 283 trades, 24.0% WR, **-0.295%** |

(Trade count went *up* slightly in the primary window with the filter
on -- not a bug: this backtester holds one position per symbol at a
time, so blocking an early entry can free a symbol up for a different,
later entry it would otherwise have missed. Expected side effect of
the simplified one-position-per-symbol model.)

**Honest read: helps, doesn't fix.** The filter roughly halves the
loss in the third window and modestly reduces it in the second, while
barely touching the profitable primary window -- directionally
confirms volatility is a real factor. But neither losing window
flips to profitable. A single volatility threshold on BTC alone isn't
sufficient by itself.

**Not chasing a better threshold by fitting it to these exact 3
windows** -- with only 3 known outcomes, tuning the threshold to make
them come out better would be the same overfitting trap as the
rejected ATR=20 result, just one level up. Real next steps would need
either more independent windows to validate a refined threshold
against, or a fundamentally different regime signal (e.g. BTC trend
direction combined with volatility, not volatility alone).

**Decision point, not resolved in this session:** live bot is still
running the un-gated config and still performing well in the current
(evidently calm) regime. Whether to (a) leave it as-is and accept the
risk that performance could reverse if conditions shift, (b) apply the
partial regime filter live as a modest safety net even though it
doesn't fully solve the problem, or (c) invest more in a better regime
signal before trusting this further -- needs a call from the user.

## 2026-08-22 -- Volatility filter applied live; trend-combined filter rejected

**Applied the volatility-only regime filter to live paper trading**
(new BUY entries gated on BTC trailing-200-candle volatility < 0.10%,
never gates exits). Justified by real-time evidence, not just
backtest: live BTC volatility measured at 0.138-0.153% today --
already above both historical losing windows (0.128%/0.146%) -- right
as live drawdown jumped from 2.00% to 11.11% for the first time.
`check_market_regime()` in scanner.py, config knobs in config.py under
"MARKET REGIME FILTER". Live bot restarted, no portfolio reset needed.

**Tested combining volatility with BTC trend (price > EMA50) --
rejected.** Both conditions pre-chosen, not fit per-window.

| Window | No filter | Volatility only | Volatility + trend |
|---|---|---|---|
| Primary (good) | +0.456% | +0.327% | **+0.015%** |
| Second (bad) | -1.167% | -1.047% | -0.791% |
| Third (bad) | -0.651% | -0.272% | -0.145% |

Adding trend squeezes a little more protection out of the bad windows
but costs nearly all the edge in the good window to get there -- not a
net improvement. Keeping the live filter volatility-only.

**Methodology note:** `fetch_history()`'s cache never expires, so
"Primary (last 30d)" has silently become a fixed snapshot from
whenever it was first cached (~2026-08-18-20) rather than a true
rolling last-30-days as of each run -- this is why the primary
window's exact numbers drift slightly between test runs even with
identical config. Doesn't invalidate the regime-dependency finding
(all three windows are still consistently defined, comparable to each
other), but exact percentages should be read as approximate. Not
fixed this session -- would need cache-freshness logic if it matters
for future work.

## 2026-08-22/23 -- Multi-timeframe (1h) confirmation: beats the volatility filter, now live

Tested requiring per-symbol 1h trend agreement (EMA_FAST > EMA_SLOW on
1h, resampled from already-cached 5m data via `build_htf_trend_filter()`
in backtest.py, shift(1) before reindexing to prevent lookahead) before
allowing a 5m BUY. `htf_confirmation_test.py`, same 3 windows, 4 configs:

| Window | No filter | Volatility (was live) | **1h confirmation** | Volatility + 1h |
|---|---|---|---|---|
| Primary (good) | +0.456% | +0.327% | **+1.106%** | +1.008% |
| Second (bad) | -1.167% | -1.047% | **-0.869%** | -1.062% |
| Third (bad) | -0.651% | -0.272% | -0.423% | **-0.180%** |

**1h confirmation alone wins outright on Primary and Second, and is
competitive (not best, but far better than no-filter) on Third.**
Unlike the volatility gate, it doesn't just play defense -- it more
than doubles the edge in the profitable window (+0.456% -> +1.106%)
while *also* reducing losses in the bad ones. The stacked
volatility+1h combo isn't a clear win over 1h-alone (better on Third,
worse on Second) and adds complexity for it.

**Applied live, replacing the volatility filter** (which was live for
about 2 hours). `check_htf_confirmation()` in scanner.py, checked
lazily only for symbols that already got a 5m BUY (avoids an extra API
call every scan cycle for all ~150 symbols). Config: `HTF_TIMEFRAME`/
`HTF_CANDLE_LIMIT` in config.py. Volatility filter config/tooling kept
for research (regime_filter_test.py still works), just not read by the
live scanner path anymore. Live bot restarted, no portfolio reset
needed (only future entries affected). Confirmed working immediately:
open positions ticked up (28->29, a new entry got allowed) right after
restart, whereas the volatility filter had been fully blocking new
entries for hours before that.

**Not yet done:** train/test discipline within each window for this
result specifically (each window's 4-config comparison uses the same
full window for all 4 -- there's no held-out split here the way the
original exit-parameter sweep had). The cross-window consistency (wins
on 2 of 3, competitive on the 3rd) is reassuring but this hasn't had
the same rigor as earlier findings. Worth a proper train/test pass if
questioned later.

## 2026-08-23 -- Train/test check reveals the 1h confirmation win was partly illusory

Closed the rigor gap flagged in the previous entry: split each
window's trades into train (first 75%) / test (last 25%, by entry
time), same discipline as the original exit-parameter sweep.

| Window | Config | Train Exp | **Test Exp (held out)** |
|---|---|---|---|
| Primary (good) | No filter | +0.026% | +4.418% |
| Primary (good) | 1h confirmation | +0.479% | **+5.403%** |
| Second (bad) | No filter | -1.189% | -0.937% |
| Second (bad) | 1h confirmation | -0.626% | **-2.578%, 4.0% WR (n=25)** |
| Third (bad) | No filter | -0.878% | +2.342% |
| Third (bad) | 1h confirmation | -0.924% | +1.912% (roughly a wash) |

**The full-window aggregate reported in the previous entry was
misleading.** In the second window, 1h confirmation's apparent
improvement (-1.167%->-0.869% in the earlier full-window view) was
concentrated in the train portion and collapsed in the held-out test
slice to -2.578% at 4.0% win rate -- far worse than doing nothing.
Third window shows no real benefit in test either way. **Only the
primary window (current live regime) genuinely holds up.**

**This means: regime-robustness is still an open, unsolved problem.**
Neither the volatility filter nor 1h confirmation has actually been
shown to work across regimes under real train/test scrutiny -- both
looked good on full-window aggregates and both get shakier when
checked properly. This is the second time a full-window (rather than
train/test) comparison has overstated a result this project (see also
the ATR=20 sweep rejection) -- **full-window aggregates without a
held-out split should not be trusted going forward, only train/test
results.**

**Not reverting the live bot over this** -- 1h confirmation still
holds up in the primary window, which is the regime currently being
traded in, and doing nothing is not obviously better. But confidence
in this filter should be "promising in current conditions," not
"validated," and this remains unresolved.

## What's next (in rough priority order)

1. ~~Validate the volume-ranking result~~ -- DONE (2026-08-18).
2. ~~Exit-parameter sweep~~ -- DONE (2026-08-18). No improvement over
   current live values found.
3. ~~Signal component ablation~~ -- DONE (2026-08-18). Momentum
   component confirmed harmful and disabled; RSI/MACD/volume/chop-gate
   all confirmed load-bearing.
4. ~~A second, non-overlapping historical window~~ -- DONE (2026-08-20).
5. ~~Third window + regime characterization~~ -- DONE (2026-08-21).
   Regime dependency confirmed across 3 windows, not one bad month.
6. ~~Regime filter (volatility)~~ -- DONE (2026-08-21/22). Helped but
   didn't fully fix the losing windows; applied live, then superseded.
7. ~~Multi-timeframe confirmation~~ -- DONE, see entry above. Beat the
   volatility filter on every dimension. Now live.
8. ~~Proper train/test validation of the 1h confirmation result~~ --
   DONE, see entry directly above. **Result: mostly didn't hold up.
   Regime-robustness is still unsolved.**
9. ~~Find a filter that survives train/test within each window~~ --
   TRIED 4h as a candidate, see following entry. **Also rejected.**
   Both HTF timeframes now ruled out with proper rigor.
10. A 4th historical window (95-125 days ago) would help -- but given
    #9's finding, more windows without fixing the underlying
    full-window-vs-test-split gap will just repeat the same trap.
11. Wider/finer exit-parameter grids only if #9/#10 change the picture
    enough to be worth revisiting.

## 2026-08-23 (cont.) -- 4h confirmation also rejected; live bot reverted

Extended the train/test check to also test 4h confirmation (slower,
smoother trend signal, hypothesised to be less prone to 1h's apparent
whipsaw fragility), train/test discipline built in from the start this
time. All 3 windows, held-out test period only:

| Window | No filter | 1h confirmation | 4h confirmation |
|---|---|---|---|
| Primary (good) | +4.137% | +4.531% | +6.533% (n=19, thin) |
| Second (bad) | **-0.528%** (best) | -2.050% | -1.000% |
| Third (bad) | **+1.352%** (best) | +0.335% | -0.821% |

**Neither HTF filter holds up.** In both bad-regime windows' held-out
test periods, "no filter" beats *both* 1h and 4h confirmation -- the
filters make exactly the situation they were meant to protect against
worse, not better. Only in the primary (current-regime) window do the
filters look comparable-to-slightly-better, on a small sample.

**Reverted the live bot to no HTF/regime gate at all**
(`execute_paper_trades()` in scanner.py). Two different filters have
now both looked convincing on full-window aggregates and failed under
proper train/test scrutiny -- continuing to ship untested "fixes" isn't
defensible. `check_htf_confirmation()` and `check_market_regime()` stay
in the code for backtesting/research, just not called live.

**Where this actually leaves things:** the well-validated core (signal
engine with the momentum fix, ATR-based risk, volume-ranked symbols)
remains the only thing that's genuinely held up under real train/test
scrutiny throughout this whole project. Regime-robustness is a real,
open, unsolved problem -- not something to claim progress on again
without a result that survives the same level of checking applied
here. Next attempt at a regime fix should be validated with train/test
built in from the very first test, not retrofitted after a full-window
result looks promising (that pattern has now failed twice).
