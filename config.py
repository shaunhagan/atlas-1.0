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