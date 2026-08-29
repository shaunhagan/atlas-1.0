# Atlas Stocks Optimization Log

Running record of stock-strategy experiments, mirroring
OPTIMIZATION_LOG.md's discipline (which was built the hard way, after
repeatedly getting burned by full-window results that didn't survive
proper scrutiny). Read this before starting new work.

**Rules (same as the crypto log):**
- Append a new dated entry, don't rewrite history.
- Every claim needs a number from `stock_backtest.py` behind it,
  ideally out-of-sample (test-period, not train-period).
- Full-window aggregates without a held-out split are NOT trustworthy
  on their own -- this has burned the project multiple times on the
  crypto side (ATR=20 rejection, both HTF confirmation attempts, and
  the split_ts bug that silently corrupted several early crypto
  validations). Do not repeat that here.
- If a change looks like a genuine improvement, open a PR / get sign-off
  before it reaches `stock_main.py`'s live config -- same rule as
  crypto's `OPTIMIZATION_LOG.md`.

---

## 2026-08-26 -- Stock trading system built; first backtest promising, does NOT survive train/test

Built the full independent stock paper-trading system (separate
portfolio, logs, process from crypto) and `stock_backtest.py` (mirrors
`backtest.py`, pointed at `stock_exchange`/Alpaca). Settings: reused
crypto's general risk philosophy (1% risk/trade, ATR-based stops --
real stock 5m ATR% checked against live data first, found comparable
in magnitude to crypto's ~0.1-0.6%), friction lowered to reflect
Alpaca's commission-free trading, and deliberately did NOT carry over
crypto's regime/HTF filters (validated specifically against BTC, never
tested for stocks).

**First full-window backtest (50 symbols, 30 days) looked strong:**
114 trades, 38.6% win rate, +8.65% avg win / -2.98% avg loss,
**+1.511% expectancy/trade**. Confidence buckets looked sensible too
(80-89 outperforming 70-79, unlike early crypto findings where higher
confidence didn't mean better outcomes).

**Did NOT trust it at face value -- ran train/test immediately**
(last 25% of trades by entry time held out, using
`optimize.compute_split_ts`/`split_trades` directly since they're
generic, not crypto-specific):

| Split | Trades | Win Rate | Expectancy |
|---|---|---|---|
| Train | 101 | 42.6% | +2.029% |
| **Test (held out)** | **13** | **7.7%** | **-2.513%** |

**The promising result does not hold up.** Same pattern as crypto's
rejected ATR=20 sweep result -- looks great in-sample, collapses
out-of-sample. Caveat: only 13 test trades is a genuinely small
sample (below the significance bar used elsewhere in this project),
so this isn't a fully conclusive rejection, just clearly not something
to trust yet either.

**Why the sample is so small:** stocks only trade ~6.5h/weekday vs
crypto's 24/7, so a 30-day calendar window yields far fewer trades for
the same symbol count (114 here vs crypto's 500+ in a comparable test).
Splitting a small total into train/test leaves very few test trades.

## 2026-08-26/27 (cont.) -- Fixed a cache bug, extended to 90 days: result confirmed negative, not just small-sample noise

Along the way, found and fixed a real bug: `_cache_path()` in both
`backtest.py` and `stock_backtest.py` didn't encode `days` in the
cache filename for the default (`end_days_ago=0`) case -- a 90-day
fetch request silently returned the previously-cached 30-day data.
Confirmed concretely (90-day AAPL request returned exactly the 30-day
candle count before the fix). Never bit crypto in practice since
`BACKTEST_DAYS=30` was always used consistently there, but it was a
live landmine. Fixed in both files; cache filenames now always include
`days`.

**Re-ran the train/test validation at 90 days** (302 train / 55 test
trades, ~4x the previous test sample):

| Split | Trades | Win Rate | Expectancy |
|---|---|---|---|
| Train | 302 | 32.5% | +0.466% |
| **Test (held out)** | **55** | **-1.021%**, 25.5% WR |

**Confirmed, not resolved by more data.** Train itself dropped
substantially too (+2.029% at 30 days -> +0.466% at 90 days), and the
held-out test stays clearly negative on a properly-sized sample. This
rules out "the first result was just small-sample noise" -- reusing
crypto's signal engine and risk parameters as-is genuinely does not
show a validated edge on stocks.

**Two honest possibilities, not yet distinguished:**
1. The parameters (ATR multiplier, risk:reward, confidence threshold)
   need stock-specific tuning, the same way crypto's did -- crypto's
   numbers were never assumed optimal for stocks, just a reasonable
   starting point.
2. The underlying signal combo (EMA/RSI/MACD) may have even less edge
   on US equities than on crypto alts -- large-cap stocks are far more
   efficiently priced/arbitraged than crypto, a concern already flagged
   on day one of this project as a risk for the crypto side too.

Can't tell which without running the actual parameter sweep first.

## 2026-08-27 -- Exit-parameter sweep: same overfitting trap as crypto's ATR=20, rejected

Ran `stock_optimize.py` (90 days, 50 symbols, same staged
coordinate-descent + train/test discipline as crypto's `optimize.py`).

**Sweep picked ATR_STOP_MULTIPLIER=20, RISK_REWARD_RATIO=2.0,
MIN_CONFIDENCE=65** -- train expectancy climbed to +1.914% as the grid
tightened, with the exact same tell as crypto's rejected ATR=20 result:
trade count collapsing as the multiplier increased (577 -> 122 trades).

**Confirmation run exposed it immediately:**

| Config | Full period | Test (held out) |
|---|---|---|
| Baseline (crypto-transplanted, ATR=10/RR=2.5/conf=70) | +0.237% | -1.021% |
| "Winner" (ATR=20/RR=2.0/conf=65) | +1.273% | **-4.664% (n=15)** |

**Rejected.** The winner looks dramatically better full-period and
collapses to a much worse, catastrophic result on the tiny (15-trade)
held-out test. Textbook overfit, same pattern as crypto's ATR=20
rejection on 2026-08-18. Exit-parameter tuning alone does not rescue
stocks -- the baseline's negative test expectancy stands unchanged.
No config change to `stock_main.py`.

## 2026-08-27 (cont.) -- Signal ablation: no rescue either; honest conclusion reached

Ran `stock_ablate.py` (90 days, 50 symbols, same train/test discipline).

| Removed | Test N | Test Exp | Verdict |
|---|---|---|---|
| trend | 0 | n/a | Structurally required (same as crypto) |
| RSI | 0 | n/a | Structurally required -- confidence never reaches MIN_CONFIDENCE without it |
| MACD | 0 | n/a | Structurally required, same reason |
| momentum | 302/55 (identical to baseline) | -1.021% | Already off by default (crypto's finding) -- this row is a no-op by construction |
| volume | 260/55 | **-0.906%** | Modest improvement, same test N as baseline (55, apples to apples), still negative |
| chop-gate | 303/55 | -1.021% (identical) | **No effect at all** -- very different from crypto, where removing this caused a 12x trade explosion (2877 vs 234 trades). The `MIN_EMA_SPREAD_PCT`/`MIN_MACD_HIST_PCT` thresholds were calibrated against crypto's price/volatility scale and may simply rarely trigger on stocks' different profile. |

**No rescue.** Best single change (dropping volume) still leaves test
expectancy negative (-0.906%), just less bad. Structurally-required
components can't be tested this way (need e.g. a MIN_CONFIDENCE drop
to compensate, not attempted here).

**Honest conclusion: three independent validation attempts (raw
crypto-transplanted config, exit-parameter sweep, component ablation)
have all failed to find a validated positive edge for this signal
engine on stocks.** This is a legitimate, useful finding, not a
failure of the process -- exactly what disciplined backtesting is
for. The EMA/RSI/MACD combination may simply not have a reliable edge
on large-cap US equities (far more efficiently priced/arbitraged than
crypto alts, a concern flagged as a real risk back on this project's
first day). **No config changes have been made to `stock_main.py`'s
live settings at any point in this research trail.**

## What's next

1. ~~Extend the backtest window~~ -- DONE (2026-08-26/27).
2. ~~Stock-specific exit-parameter sweep~~ -- DONE (2026-08-27).
   **Rejected.**
3. ~~Signal component ablation~~ -- DONE, see entry above. **No
   rescue found. Honest conclusion: no validated edge yet.**
4. **Live stock paper trading continues as-is, purely observational
   for now** -- worth watching whether live results (different
   symbols/timing than the backtest window) tell a different story,
   the same way crypto's live results eventually diverged positively
   from an early rough patch.
5. **Untested ideas if this is worth pursuing further later:** test
   `use_momentum=True` specifically for stocks (crypto and stocks
   could plausibly behave oppositely here, never actually tested since
   it's off by default); a completely different indicator combination
   rather than reusing crypto's; a larger/different symbol universe
   (mega-cap only? higher volume filter?) than the current
   volume-ranked top 50.
6. **Not recommended:** more exit-parameter or ablation variations on
   the current signal engine without a new hypothesis -- three
   attempts have already come up empty; more of the same is unlikely
   to change that.

## 2026-08-27 -- Momentum-enabled tested directly: also worse, not better

Tested `use_momentum=True` explicitly for stocks (previously only
ever tested implicitly via the ablation's default-off baseline).
Comparable sample sizes (292/302 train, 53/55 test):

| Config | Test N | Test Expectancy |
|---|---|---|
| Momentum OFF (current default) | 55 | -1.021% |
| Momentum ON | 53 | **-1.583%** (worse) |

**Confirms the current default is correct for stocks too** -- momentum
doesn't help either asset class, not a case of crypto and stocks
behaving oppositely as hypothesized. Not a rescue, but closes off one
of the untested ideas cleanly. Remaining untested ideas (different
indicator combo, different universe) are bigger undertakings than a
quick toggle test -- parking stock strategy research here for now
given four independent attempts have all come up empty; revisit with
a genuinely new hypothesis rather than more of the same.

## 2026-08-27 -- Major finding: the symbol universe was never actually volume-ranked

While monitoring the live bot, found `stock_exchange.py`'s `get_ticker()`
throwing an uncaught `KeyError` 225 times on a symbol called `AAGIY`
(fixed separately). Looking at *why* AAGIY -- a thinly-traded ADR -- was
even in the live scan universe exposed something bigger: `get_markets()`
was sorting `symbols.sort()` **alphabetically** and taking the first 50,
not ranking by volume. "What's next" item 5 above, written earlier in
this log, incorrectly assumed "the current volume-ranked top 50" -- it
never was. Crypto's `exchange.py` had this exact bug and was fixed for
it early in the project (2026-08-1x); the fix was never mirrored here.

**This means every stock validation result above -- the raw
crypto-transplanted backtest, the exit-parameter sweep, the ablation,
and the momentum test -- was run against an arbitrary, early-alphabet
symbol set** (AAGIY, AAL, AABB-style names), not the liquid mega-caps
("current volume-ranked top 50") the analysis assumed. All four "no
validated edge" conclusions above may be an artifact of the universe,
not the signal engine.

**Fixed**: `get_markets()` now ranks by Alpaca's most-actives screener
(`ScreenerClient.get_most_actives`, by volume, capped at the API's
top=100 limit) and filters that ranked list down to tradable+
fractionable symbols, falling back to fill any remaining slots
alphabetically only if the ranked list comes up short. New top-50
sample: NVDA, INTC, AMZN, MSTR, PLTR, SOFI, BAC, F, SPY, CRM, and
other genuinely liquid, widely-traded names -- a completely different
universe from before.

**This invalidates the "no edge" conclusion above as untested-on-the-
right-data, not confirmed-negative.** Re-running the full validation
sequence (backtest -> train/test -> sweep -> ablation) against the
corrected universe is the obvious next step, in progress below.

## 2026-08-27 (cont.) -- Regime filter test, but caveat: ran on the OLD universe

`stock_regime_test.py` (SPY-based analogue of crypto's BTC volatility
filter) had already started running in the background before the
`get_markets()` fix above landed -- Python doesn't hot-reload a running
process's imports, so it completed against the old alphabetical
universe. Trade counts (302 train / 55 test) exactly match the earlier
momentum-test entry, confirming this. Recording for completeness, not
as a trustworthy result:

| Config | Train N | Train Exp | Test N | Test Exp |
|---|---:|---:|---:|---:|
| No filter | 302 | +0.466% | 55 | -1.021% |
| Volatility only | 212 | -0.374% | 77 | -0.593% |
| Volatility + trend | 186 | -0.310% | 72 | -1.015% |

Directionally the same story as no-filter (all still negative), so the
regime filter doesn't look like a rescue either way -- but this needs
re-running on the corrected universe before trusting it. Queued.

## 2026-08-27 (cont.) -- Re-validated on the corrected universe: conclusion holds, more cleanly

New universe (post `get_markets()` fix): NVDA, INTC, AMZN, MSTR, PLTR,
SOFI, BAC, F, SPY, CRM, TQQQ/SQQQ, and other genuinely liquid,
high-volume names -- nothing like the old alphabet-soup set.

**30-day full-window looked promising again** (`stock_traintest`
smoke check): 157 trades, 38.9% win rate, +1.198% expectancy. Same
shape as the very first (flawed-universe) result on day one of stock
research -- a reminder not to trust a 30-day full-window number here
regardless of which universe it's testing, per the sample-size finding
from 2026-08-26/27.

**90-day backtest + train/test (`stock_traintest.py`), the number that
actually matters:**

| Metric | Full period | Train | Test (held out) |
|---|---:|---:|---:|
| Trades | 544 | 465 | 79 |
| Win Rate | 26.7% | 27.1% | 24.1% |
| Expectancy/Trade | **-0.567%** | **-0.521%** | **-0.840%** |

**Conclusion holds, and more cleanly than before.** Negative on all
three cuts (full/train/test) rather than a train-up/test-down
overfitting shape -- this isn't a sample-quality artifact, it's a
consistent, honest negative. The universe-selection bug was real and
worth fixing regardless (trading actual liquid names has better real-
world execution characteristics and stops the AAGIY-style API errors
entirely on its own merits), but it does **not** rescue the earlier
finding: **the EMA/RSI/MACD signal engine still shows no validated
edge on US equities**, now confirmed on both a flawed and a corrected
universe. This closes off "maybe it was just the wrong symbols" as a
live hypothesis.

**Updated bottom line: five independent validation attempts (raw
config, exit-param sweep, ablation, momentum toggle, and now a
corrected symbol universe) have all failed to find a validated
edge for this signal engine on stocks.** Live stock paper trading
continues as-is, observational only -- same status as before, just on
firmer footing now that the universe question is closed.

## 2026-08-29 -- Structurally different strategy: Bollinger Band + RSI mean reversion

Five straight rejections of the EMA/RSI/MACD trend engine raised the
question of whether the *asset class* has no edge, or the *strategy
type* is wrong for it. External research: momentum/trend strategies are
widely documented to underperform specifically in efficiently-priced,
heavily-arbitraged large-cap equities (high turnover/transaction-cost
drag, frequent false breakouts), while mean-reversion has real evidence
at intraday timeframes -- worth testing as a structurally different
approach rather than another retune of an engine already shown dead.

Built `stock_meanrev_backtest.py`: BUY when price closes at/below the
lower Bollinger Band (20-period, 2 stddev) AND RSI < 30 -- long-only,
same ATR-based bracket exit/position mechanics as the trend engine, so
only the entry signal differs (apples-to-apples comparison, not a
confound). New `Indicators.bollinger_bands()`, new `BOLLINGER_*` /
`MEANREV_RSI_*` config (research-only, not read by any live path yet).

**Window 1 (last 90 days) -- mixed:**

| Split | Trades | Win Rate | Expectancy |
|---|---:|---:|---:|
| Train | 487 | 27.1% | -0.482% |
| Test (held out) | 76 | 42.1% | **+1.366%** |

Train negative, test positive -- the opposite of the classic
overfitting shape (which would be train-good/test-bad), but a strategy
whose sign flips between cuts isn't a confirmed edge on its own either.
Didn't stop at one ambiguous window -- ran a second, non-overlapping
90-180-days-ago window (`stock_meanrev_window2.py`) to check whether
the positive test result replicates or was a fluke, mirroring the
multi-window discipline `regime_filter_traintest.py` already uses for
crypto.

**Window 2 (90-180 days ago) -- clean, both cuts positive:**

| Split | Trades | Win Rate | Expectancy |
|---|---:|---:|---:|
| Train | 477 | 36.7% | **+1.601%** |
| Test (held out) | 116 | 27.6% | **+0.649%** |

**Combined picture, focusing on the only numbers this log trusts
(held-out test periods, never touched by tuning):** window 1 test
+1.366%, window 2 test +0.649% -- **positive in both independent
windows.** This is the first time in this entire stock research trail
(six attempts now, five for the trend engine plus this one) that a
held-out test result has been positive more than once, let alone
consistently across non-overlapping windows.

**Not yet a green light to deploy live.** This is a promising,
replicating signal, not a fully closed case -- window 1's train
result being negative deserves a robustness check (parameter
sensitivity, maybe a third window) before touching `stock_main.py`,
consistent with this log's own rule: "if a change looks like a genuine
improvement, open a PR / get sign-off before it reaches live config."
Next: parameter sweep on the BB period/stddev and RSI threshold, plus
a decision on whether to run this as a new live path alongside (not
replacing) the trend engine, or swap it in -- worth a direct
conversation given it would be the biggest live change yet.

## 2026-08-29 (cont.) -- Parameter robustness sweep reveals regime dependency, not a clean win

Swept BB stddev (1.5/2.0/2.5) x RSI oversold threshold (25/30/35), 9
combinations, on both windows (`stock_meanrev_robustness.py`, reusing
already-cached candle data).

**Window 2 (90-180d ago): robust across the whole grid.** TRAIN
positive in all 9 combinations (+1.04% to +1.82%). TEST positive in
7/9, only slightly negative in the other 2 (-0.26%, -0.52%). Not a
lucky single combination -- this window's edge is real and holds up
across nearby parameter choices.

**Window 1 (last 90d): a different, important signal.** TRAIN is
**negative in all 9/9 combinations** (-0.13% to -0.91%), regardless
of parameters -- this isn't noise or a bad parameter pick, the entire
most-recent-90-day period was unfavourable for this strategy shape.
TEST (the most recent ~3 weeks specifically) is positive in 8/9, but
given train's uniform negativity across the whole grid, that reads
more like a short recent bounce than a stable edge holding in current
conditions.

**Honest conclusion: this is not "mean reversion works," it's "mean
reversion works well in some regimes and poorly in others."** Matches
the external research directly -- mean-reversion strategies are
documented to fail in strong trends, momentum strategies fail in
ranges, and regime recognition is "the master skill." Window 2 was
apparently more range-bound (great for this approach); window 1 was
apparently more trending (bad for it, consistent with the *trend*
engine also failing everywhere -- if trend-following was failing due
to false-breakout whipsaw rather than absence of trends, both
readings would need reconciling, worth checking later).

**Not deploying to `stock_main.py` on this evidence.** It's a
genuinely better-evidenced strategy than the trend engine (which
never once showed a positive train result in five attempts), but
"regime-dependent, sometimes strongly negative" is not the same as
"validated edge" without pairing it with a regime filter to sit out
the bad periods -- exactly the gap that made window 1's train
negative. Flagging for a direct conversation: build a regime filter
for this specifically (a range/trend detector, not the crypto BTC-
volatility one which doesn't transfer -- see meme's rejected transfer
attempt for why asset-class transfer needs re-validating, not assuming),
run mean-reversion as a new parallel live path rather than replacing
the trend engine, or continue stocks as purely observational until a
regime-aware version validates. No live change made.
