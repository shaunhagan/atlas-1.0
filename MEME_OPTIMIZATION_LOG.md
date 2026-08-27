# Atlas AI -- Meme Coin Tier Research Log

Append-only. Same discipline as OPTIMIZATION_LOG.md / STOCK_OPTIMIZATION_LOG.md:
every finding recorded with real numbers, including constraints and rejected
ideas, not just wins.

---

## 2026-08-27 -- Kraken OHLCV history depth limitation (discovered)

Built `meme_backtest.py` mirroring `stock_backtest.py`'s structure, pointed at
`meme_exchange` (Kraken) and `MEME_*` config. First smoke test requesting 30
days of 5m candles for DOGE/USD, FARTCOIN/USD, PENGU/USD returned only 721
candles (~2.5 days), not ~8640 (30 days).

Verified this is a genuine Kraken public API limitation, not a bug in our
pagination/caching: called raw `ccxt.kraken().fetch_ohlcv(..., since=<30 days
ago>, limit=1000)` directly, got the identical 721-candle, ~2.5-day result.
Kraken's OHLC endpoint does not support deep historical pagination via
`since` the way Binance/Alpaca do -- it just returns its own most recent
window regardless of what's requested.

At ~2.5 days across 22 symbols this would have produced a very thin sample
(smoke test suggested well under 100 total trades), too small for a
meaningful 75/25 train/test split (recall `MIN_TRADES_FOR_SIGNIFICANCE = 20`
in optimize.py -- a test bucket that size on its own is barely above that
bar, no margin for splitting further per-symbol or per-confidence-bucket).

## 2026-08-27 -- Fix: Binance-sourced backtest history for cross-listed symbols

Checked overlap between the 22 Kraken meme coin candidates and Binance's
active `/USDT` markets: 14/22 are cross-listed (DOGE, SHIB, PEPE, WIF, BONK,
FLOKI, MEME, MUBARAK, TURBO, NEIRO, PNUT, ACT, TRUMP, PENGU).

`meme_backtest.fetch_history()` now tries `{base}/USDT` on Binance first (via
the existing `exchange` module, unmodified, same deep-pagination code path
`backtest.py` already uses) and only falls back to Kraken's native ~2.5-day
window for the 8 symbols not listed there (FARTCOIN, SPX, POPCAT, MOODENG,
GIGA, PONKE, GOAT, MEW).

This is backtesting-only. Live trading still executes on Kraken exclusively
(the UK-accessibility/legitimacy reasoning that picked Kraken over
Gate.io/KuCoin was about live execution, not historical data sourcing). The
substitution is reasonable rather than distorting: these are the same
underlying asset, and major meme coins are actively arbitraged across large
exchanges, so USD (Kraken) vs USDT (Binance) price action tracks closely for
the liquid, cross-listed names.

Result: DOGE/USD went from 721 candles (2.5 days) to 8640 candles (30 days,
matching Binance's real 5m history depth) after the fix.

## 2026-08-27 -- Full-window backtest (baseline, current live settings)

22 symbols, 30 days (hybrid-sourced), current live config
(MEME_ATR_STOP_MULTIPLIER=6.0, MEME_RISK_REWARD_RATIO=3.5,
MEME_MIN_CONFIDENCE=55, MEME_TRADING_FRICTION_PCT=0.0015):

- Total trades: 376
- Win rate: 27.1% (102W / 274L)
- Average win: +9.44% / Average loss: -2.50%
- Expectancy: +0.739%/trade

Low win rate is expected and by design for this tier -- wide 6x ATR stop and
3.5:1 reward:risk means most trades lose small and a minority win big. Same
shape as a trend-following/breakout system, consistent with meme coins'
actual price behaviour (long quiet stretches, occasional violent moves).

## 2026-08-27 -- Train/test validation (`meme_traintest.py`)

Split boundary computed from the cached data's own timestamp span via
`optimize.compute_split_ts()` (same fixed function crypto/stocks use --
anchored to the data, not live wall-clock time, so results are reproducible
regardless of when the script is re-run). Last 25% of the 30-day window held
out as TEST, never touched by symbol/parameter selection.

Caveat: the 8 Kraken-native-only symbols (2.5-day history) fall entirely
inside the TEST window by construction -- they contribute 0 trades to TRAIN.
Reported both the full TEST set and a symbol-matched subset (only the 14
Binance-sourced symbols that also appear in TRAIN) to keep the comparison
honest.

| Bucket                          | Trades | Win rate | Expectancy/trade |
|----------------------------------|-------:|---------:|------------------:|
| TRAIN                             |    275 |    25.1% |            +0.502% |
| TEST (full, incl. Kraken-native) |    101 |    32.7% |            +1.384% |
| TEST (symbol-matched to TRAIN)   |     81 |    34.6% |            +1.719% |

Held-out performance is positive and, on the symbol-matched comparison,
stronger than the training-period result -- the opposite of the overfitting
signature (train looking good, test collapsing) seen and rejected for HTF
confirmation on crypto twice. Current live meme coin settings pass this
validation check: **kept as-is, no config change made.**

Sample size note: 275 train / 101 test trades is comparable in order of
magnitude to the crypto/stock validation runs that informed prior go/no-go
calls in OPTIMIZATION_LOG.md and STOCK_OPTIMIZATION_LOG.md.

## 2026-08-27 -- Signal component ablation (`meme_ablate.py`)

Same split (`optimize.compute_split_ts`), 30-day hybrid-sourced window, all 6
signal components tested one-removed-at-a-time against the current live
baseline:

| Config                | Train N | Train Exp | Test N | Test Exp |
|------------------------|--------:|----------:|-------:|---------:|
| ALL (current live)     |     275 |   +0.502% |    101 |  +1.384% |
| WITHOUT use_trend       |       0 |    (n/a)  |      0 |   (n/a)  |
| WITHOUT use_rsi         |     288 |   +0.359% |    104 |  +0.880% |
| WITHOUT use_macd        |     234 |   +0.749% |     94 |  +0.858% |
| WITHOUT use_momentum    |     275 |   +0.502% |    101 |  +1.384% |
| WITHOUT use_volume      |     284 |   +0.624% |     97 |  +0.897% |
| WITHOUT use_chop_gate   |     274 |   +0.502% |    103 |  +1.357% |

Findings:
- **use_trend is load-bearing**: removing it produces zero trades at
  MEME_MIN_CONFIDENCE=55 -- the trend component alone appears to supply
  enough of the confidence score for anything to clear the bar. Can't be
  meaningfully ablated this way; not itself a finding of harm, just
  confirms it's structurally necessary given the current threshold.
- **RSI, MACD, volume all pull their weight**: each removal looks
  neutral-to-better on TRAIN (MACD +0.749%, volume +0.624%, both above
  baseline's +0.502%) but *worse* on TEST (+0.858%, +0.897%, both below
  baseline's +1.384%) -- the classic train-up/test-down overfitting
  shape this project has flagged before (HTF confirmation, crypto,
  rejected twice for the same pattern). Kept as-is.
- **use_momentum is a no-op here**: identical numbers with/without it,
  because it already defaults to False live (the crypto ablation finding
  that flipped this default applies globally, not per-asset-class) --
  expected, not a new result.
- **use_chop_gate has negligible effect on meme coins**: 274 vs 275
  train trades, +1.357% vs +1.384% test expectancy -- essentially
  unchanged. Plausible explanation: meme coins are rarely in the flat/
  choppy regime this gate is designed to catch, so it seldom fires for
  this asset class. Not harmful, left in for consistency with crypto/
  stocks rather than removed on a marginal, likely-noise difference.

**Conclusion: current live signal configuration is confirmed best-or-tied
on every component, on the held-out test period. No config change made.**

## 2026-08-27 -- Parameter sweep (`meme_optimize.py`) -- REJECTED

Staged coordinate-descent sweep over MEME_ATR_STOP_MULTIPLIER (3-10),
MEME_RISK_REWARD_RATIO (2-4.5), MEME_MIN_CONFIDENCE (50-70), train period
only, same 30-day hybrid-sourced window/split as the ablation above.

Every grid walked monotonically toward its extreme: wider stop → higher
train expectancy but collapsing trade count (860 trades at ATR=3, only 90
at ATR=10); higher R:R → higher train expectancy, same shrinking-N pattern
(126 trades at R:R=2, 83 at R:R=4.5); lower confidence → marginally higher
train expectancy. Winning combination: ATR=10, R:R=4.5, MIN_CONFIDENCE=50,
train expectancy +3.909%.

Confirmation against the held-out TEST period rejects it outright:

| Config                          | Trades | Win Rate | Expectancy/Trade |
|-----------------------------------|-------:|---------:|------------------:|
| Baseline - full period             |    376 |    27.1% |            +0.739% |
| Baseline - TEST (held out)         |    101 |    32.7% |            +1.384% |
| Winner - full period                |    120 |    30.0% |            +2.820% |
| Winner - TEST (held out)            |     24 |    12.5% |            -1.534% |

This is the same overfitting shape already documented and rejected for
crypto's ATR_STOP_MULTIPLIER=20 sweep result and HTF confirmation (twice):
looks great in-sample, sample size shrinks as the grid pushes toward its
extreme, and the "improvement" is noise concentrated in a handful of
outsized winning trades rather than a real edge -- 24 test trades is far
too few to trust (below MIN_TRADES_FOR_SIGNIFICANCE=20 in spirit even
though it technically clears the bar).

**Rejected. Live config unchanged: MEME_ATR_STOP_MULTIPLIER=6.0,
MEME_RISK_REWARD_RATIO=3.5, MEME_MIN_CONFIDENCE=55.** Combined with the
ablation result above, the meme tier's original hand-picked settings have
now been through the same validation sequence as crypto and stocks
(backtest -> train/test -> parameter sweep -> ablation) and held up at
every stage without needing a single change.

## 2026-08-27 -- Regime filter test on meme coins (`meme_regime_test.py`) -- REJECTED

meme_scanner.py's execute_paper_trades() was launched with no regime/HTF
gate, deliberately, as the aggressive tier -- but that was a reasonable
default, never actually tested. Crypto's BTC-volatility regime filter is
validated and live there (OPTIMIZATION_LOG.md, 2026-08-23); worth checking
whether the same market-wide risk-off gate helps or hurts meme coins
specifically, since meme coins are typically more sentiment-driven than
large caps and might behave oppositely (pumping precisely during
high-volatility/high-attention windows rather than calm ones).

Same BTC volatility filter (`regime_filter_test.build_regime_filters`,
<0.10% realised vol, BTC-sourced via Binance) and volatility+trend variant
applied as a gate on meme coin entries, same 30-day hybrid window/split:

| Config                    | Train N | Train Exp | Test N | Test Exp |
|----------------------------|--------:|----------:|-------:|---------:|
| No filter (current live)   |     275 |   +0.502% |    101 |  +1.384% |
| Volatility only             |     259 |   +0.072% |     14 |  -3.023% |
| Volatility + trend           |     252 |   +0.058% |     14 |  -3.023% |

Unlike the parameter sweep rejection above, this isn't an overfitting
artifact -- expectancy degrades on TRAIN too (+0.502% -> +0.072%), not just
test, so it's not "looks good in-sample, fails out-of-sample," it's
"actively worse throughout." The filter also collapses test trade count
from 101 to 14 (BTC was apparently in its "high volatility" state for most
of the held-out window, and that's exactly when meme coins found their
opportunities). Confirms the hypothesis: gating meme coin entries on
crypto-market calm is the wrong shape of filter for this asset class.

**Rejected. Confirms the original design choice (no regime/HTF gate on the
meme tier) was correct, not just untested.**

## Next steps (not yet done)

None outstanding. The meme tier has now been through backtest, train/test,
ablation, parameter sweep, and a regime-filter transfer check -- every
stage confirmed the original hand-picked settings and design (aggressive,
no regime gate) rather than finding something to change.
