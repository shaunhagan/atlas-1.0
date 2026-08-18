"""
=========================================
ATLAS AI
Exchange Interface
=========================================
"""

import ccxt

from config import (
    EXCHANGE,
    TIMEFRAME,
    CANDLE_LIMIT,
    SCAN_LIMIT
)


class Exchange:

    def __init__(self):

        if EXCHANGE.lower() == "binance":

            self.exchange = ccxt.binance({
                "enableRateLimit": True,
                "options": {
                    "defaultType": "spot"
                }
            })

        else:
            raise Exception(f"Exchange '{EXCHANGE}' not supported.")

    def get_markets(self):
        """
        Return the SCAN_LIMIT most liquid active USDT spot pairs,
        ranked by 24h quote volume rather than alphabetically --
        an alphabetical cap arbitrarily favours early-alphabet
        tickers and can miss high-volume/high-interest pairs
        (including major memecoins) that just happen to sort late.
        """

        markets = self.exchange.load_markets()

        candidates = [
            symbol
            for symbol, market in markets.items()
            if (
                symbol.endswith("/USDT")
                and market["active"]
                and market["spot"]
            )
        ]

        # No symbols filter: Binance returns every ticker in one
        # request this way. Passing an explicit list of ~500+
        # symbols instead blows the exchange's URL length limit.
        tickers = self.exchange.fetch_tickers()

        candidates.sort(
            key=lambda symbol: (
                tickers.get(symbol, {}).get("quoteVolume") or 0
            ),
            reverse=True,
        )

        return candidates[:SCAN_LIMIT]

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


exchange = Exchange()