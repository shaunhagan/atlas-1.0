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

## Next steps (not yet done)

- A parameter sweep (`meme_optimize.py`, mirroring `optimize.py`/
  `stock_optimize.py`) over MEME_ATR_STOP_MULTIPLIER /
  MEME_RISK_REWARD_RATIO / MEME_MIN_CONFIDENCE has not been run yet -- current
  settings are validated as reasonable, not yet confirmed optimal.
- Signal component ablation (`meme_ablate.py`, mirroring `ablate.py`) not yet
  run -- unknown whether all signal components (trend/RSI/MACD/volume) pull
  their weight for meme coins specifically, given crypto's own ablation found
  momentum actively harmful there.
