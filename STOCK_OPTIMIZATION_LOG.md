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

## What's next

1. ~~Extend the backtest window~~ -- DONE (2026-08-26/27). Confirmed
   the negative result on a properly-sized sample, not a small-sample
   artifact.
2. ~~Stock-specific exit-parameter sweep~~ -- DONE, see entry above.
   **Rejected** -- same overfitting trap as crypto's ATR=20. Exit
   tuning alone doesn't rescue stocks.
3. **Signal component ablation** -- same approach as crypto's
   momentum-component finding (`ablate.py`/`use_trend`/`use_rsi`/etc.
   toggles already exist in `signals.py`, generic, not crypto-specific).
   Test whether any single component (RSI, MACD, momentum, volume,
   chop-gate) is actively unhelpful for equities specifically, same
   train/test discipline throughout.
4. **Do not deploy any stock-specific tuning live until it survives
   train/test on a properly-sized sample.** No config changes to
   `stock_main.py`'s live settings so far.
5. If ablation doesn't turn up a fix either, the honest conclusion
   becomes: this signal combo (EMA/RSI/MACD) may just not have a
   reliable edge on US equities, which are more efficiently priced
   than crypto alts -- a real, valid outcome to land on, not a failure
   to keep chasing indefinitely.
6. Live stock paper trading continues regardless, accumulating its own
   real track record in parallel with backtesting.
