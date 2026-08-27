"""
ATLAS AI
Central Configuration
"""

# ============================================================
# MARKET SETTINGS
# ============================================================

EXCHANGE = "binance"

TIMEFRAME = "5m"

SCAN_LIMIT = 150

CANDLE_LIMIT = 200

SCAN_INTERVAL = 30


# ============================================================
# STOCK SETTINGS (Alpaca)
# ============================================================

STOCK_TIMEFRAME_MINUTES = 5

STOCK_SCAN_LIMIT = 50

STOCK_CANDLE_LIMIT = 200

STOCK_SCAN_INTERVAL = 30

# Separate paper portfolio/capital from crypto -- same starting
# balance for a fair side-by-side comparison, independently tracked.

STOCK_STARTING_BALANCE = 10000.00

# Roughly proportional to crypto's 30/150, given a 50-symbol universe.

STOCK_MAX_OPEN_TRADES = 15

STOCK_RISK_PER_TRADE = 0.01

# Real stock 5m ATR%% (checked against live data, 2026-08-26) is
# 0.05-0.51%% -- comparable in magnitude to crypto's, so reusing
# crypto's multiplier as a starting point is reasonable, NOT because
# it's assumed optimal for stocks. Needs the same kind of backtest
# validation crypto went through before being trusted further.

STOCK_ATR_STOP_MULTIPLIER = 10.0

STOCK_RISK_REWARD_RATIO = 2.5

# Alpaca stock trading is commission-free (unlike Binance's ~0.1%
# taker fee that crypto's friction estimate is based on) -- this is
# just a slippage buffer, not a fee approximation.

STOCK_TRADING_FRICTION_PCT = 0.0003


# ============================================================
# SCANNER SETTINGS
# ============================================================

SHOW_TOP = 20

MIN_CONFIDENCE = 70


# ============================================================
# PAPER / LIVE TRADING
# ============================================================

PAPER_TRADING = True

LIVE_TRADING = False

STARTING_BALANCE = 10000.00


# ============================================================
# RISK MANAGEMENT
# ============================================================

# Fraction of starting balance risked on a single trade's
# stop-loss distance.

RISK_PER_TRADE = 0.01

# Stop-loss/take-profit are volatility-adaptive (ATR-based)
# rather than a fixed percentage, so noisy low-cap pairs get a
# proportionally wider stop than calm ones instead of getting
# clipped by ordinary volatility.

ATR_PERIOD = 14

# ATR is measured on 5-minute candles but positions are often
# held for hours, so a "textbook" 2-3x multiplier (tuned for
# stops reacting within the same timeframe as the ATR) comes out
# far too tight here — observed 14-period 5m ATR on real pairs is
# only ~0.1-0.6% of price. 10x brings typical stop distance into
# the low single-digit percent range. This is a reasoned estimate
# from live data, not a backtested-optimal value.

ATR_STOP_MULTIPLIER = 10.0

RISK_REWARD_RATIO = 2.5

MAX_OPEN_TRADES = 30


# ============================================================
# EXECUTION COSTS
# ============================================================

# Applied to both entry and exit fills to approximate real-world
# cost. Binance spot taker fee is ~0.1%; the remainder is a
# slippage buffer for scanning many altcoins with a several-second
# gap between decision and fill. Applied on both sides, so a full
# round trip costs ~2x this.

TRADING_FRICTION_PCT = 0.0015


# ============================================================
# DAILY LOSS CIRCUIT BREAKER
# ============================================================

# If a book's equity drawdown from its own start-of-day baseline
# exceeds this, new entries pause for the rest of the day -- existing
# positions are still managed (stop-loss/take-profit) normally, never
# gated. Applies independently to crypto and stocks (each tracks its
# own baseline). Crypto has already seen an 11.4% max drawdown with
# nothing in place to stop a genuinely bad stretch from going further;
# 5% is a starting estimate, not backtested-optimal.

DAILY_LOSS_LIMIT_PCT = 5.0


# ============================================================
# MARKET REGIME FILTER (live)
# ============================================================

# New BUY entries are gated on BTC's own trailing volatility staying
# below this threshold; existing position exits (stop-loss/take-profit)
# are NEVER gated by this, only new entries. Was live 2026-08-22,
# briefly superseded by multi-timeframe (HTF) confirmation which looked
# better on full-window backtests -- but HTF confirmation (both 1h and
# 4h) failed proper train/test validation, while this filter passed it
# (held-out test period flips positive in both bad-regime windows, on a
# larger sample). Re-deployed 2026-08-23 (OPTIMIZATION_LOG.md).

REGIME_SYMBOL = "BTC/USDT"

REGIME_LOOKBACK = 200

REGIME_VOLATILITY_THRESHOLD_PCT = 0.10


# ============================================================
# MULTI-TIMEFRAME CONFIRMATION (research/backtesting only, NOT live)
# ============================================================

# Tried at both 1h and 4h, both looked good on full-window backtests
# and both FAILED train/test validation -- made held-out test
# performance worse than no filter at all in both bad-regime windows
# (OPTIMIZATION_LOG.md, 2026-08-23). Kept for backtest.py research
# use (require_htf_confirmation), not read by the live scanner path.

HTF_TIMEFRAME = "1h"

HTF_CANDLE_LIMIT = 100


# ============================================================
# TECHNICAL INDICATORS
# ============================================================

EMA_FAST = 20

EMA_SLOW = 50

RSI_PERIOD = 14

MACD_FAST = 12

MACD_SLOW = 26

MACD_SIGNAL = 9


# ============================================================
# TREND STRENGTH FILTER
# ============================================================

# Minimum distance between EMA20 and EMA50,
# expressed as a percentage of current price.

MIN_EMA_SPREAD_PCT = 0.10

# Minimum MACD histogram strength,
# expressed as a percentage of current price.

MIN_MACD_HIST_PCT = 0.005


# ============================================================
# LIQUIDITY FILTER
# ============================================================

# Lookback window for average volume.

VOLUME_PERIOD = 20

# Current candle volume must be at least this multiple of the
# recent average to count as confirmed by real participation.

MIN_VOLUME_RATIO = 1.0


# ============================================================
# FUTURE MODULES
# ============================================================

ENABLE_CRYPTO = True

ENABLE_FOREX = False

ENABLE_STOCKS = False

ENABLE_NEWS_FILTER = False

ENABLE_AI = False

ENABLE_MEME_ENGINE = False


# ============================================================
# LOGGING
# ============================================================

SAVE_LOGS = True

SAVE_TRADES = True

DEBUG_MODE = False