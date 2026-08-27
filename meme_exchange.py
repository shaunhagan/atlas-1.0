"""
=========================================
ATLAS AI
Meme Coin Exchange Interface (Kraken)
=========================================

Mirrors exchange.py's interface, using Kraken instead of Binance for
the high-risk meme coin tier -- broader meme coin coverage than
Binance and, unlike Gate.io/KuCoin, genuinely UK-accessible and
FCA-registered (see config.py's MEME COIN SETTINGS comment for the
comparison that led to this choice). Public market data only, no API
key needed, same as exchange.py.
"""

import ccxt

from config import (
    TIMEFRAME,
    CANDLE_LIMIT,
    MEME_SYMBOL_CANDIDATES,
    MEME_SCAN_LIMIT,
)


class MemeExchange:

    def __init__(self):

        self.exchange = ccxt.kraken({
            "enableRateLimit": True,
        })

    def get_markets(self):
        """
        Return the MEME_SCAN_LIMIT most liquid candidates that are
        actually active on Kraken right now, ranked by 24h quote
        volume. MEME_SYMBOL_CANDIDATES are base symbols (e.g. "DOGE"),
        not full pairs -- Kraken mostly quotes meme coins against USD,
        only a handful also have USDT, so each base symbol resolves
        to {base}/USD first, falling back to {base}/USDT.
        """

        markets = self.exchange.load_markets()

        def resolve(base):

            for quote in ("USD", "USDT"):

                symbol = f"{base}/{quote}"

                if (
                    symbol in markets
                    and markets[symbol]["active"]
                    and markets[symbol]["spot"]
                ):
                    return symbol

            return None

        candidates = [
            symbol
            for symbol in (resolve(base) for base in MEME_SYMBOL_CANDIDATES)
            if symbol is not None
        ]

        tickers = self.exchange.fetch_tickers(candidates) if candidates else {}

        candidates.sort(
            key=lambda symbol: (
                tickers.get(symbol, {}).get("quoteVolume") or 0
            ),
            reverse=True,
        )

        return candidates[:MEME_SCAN_LIMIT]

    def get_ticker(self, symbol):

        return self.exchange.fetch_ticker(symbol)

    def get_candles(self, symbol):

        return self.exchange.fetch_ohlcv(
            symbol,
            timeframe=TIMEFRAME,
            limit=CANDLE_LIMIT
        )

    def get_historical_candles(self, symbol, since=None, limit=1000):
        """Fetch one page of historical OHLCV candles for backtesting."""

        return self.exchange.fetch_ohlcv(
            symbol,
            timeframe=TIMEFRAME,
            since=since,
            limit=limit
        )

    def now_ms(self):

        return self.exchange.milliseconds()


exchange = MemeExchange()
