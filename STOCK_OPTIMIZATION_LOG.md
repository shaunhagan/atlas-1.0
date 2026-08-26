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

## What's next

1. **Extend the backtest window** (e.g. 90 days instead of 30) to get
   a bigger, more statistically meaningful sample -- the direct fix for
   the small-test-bucket problem, not a new experiment. Check Alpaca's
   free-tier IEX historical depth supports it first.
2. **Do not deploy any stock-specific tuning live until it survives
   train/test on a properly-sized sample.** No config changes to
   `stock_main.py`'s live settings from this entry.
3. Once there's a big enough sample, repeat crypto's validation
   sequence: exit-parameter sweep, signal component ablation, second
   non-overlapping window -- in that order, same discipline.
4. Live stock paper trading continues regardless, accumulating its own
   real track record in parallel with backtesting.
