"""
=========================================
ATLAS AI
Stock Exchange Interface (Alpaca)
=========================================

Mirrors exchange.py's interface (get_markets / get_ticker /
get_candles / get_historical_candles / now_ms) so the existing
scanner -> indicators -> signal engine -> paper_trader pipeline
can run against equities exactly like it runs against crypto,
with candles returned in the same
[timestamp, open, high, low, close, volume] shape ccxt uses.

Requires ALPACA_API_KEY / ALPACA_SECRET_KEY in a .env file
(see .env.example). Uses Alpaca's paper-trading data feed only --
Atlas's own paper_trader.py/portfolio.py still do the simulated
trading, so no orders are ever submitted to Alpaca.
"""

import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass, AssetStatus

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import DataFeed

from config import (
    STOCK_TIMEFRAME_MINUTES,
    STOCK_SCAN_LIMIT,
    STOCK_CANDLE_LIMIT,
)

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")


class StockExchange:

    def __init__(self):

        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:

            raise Exception(
                "Alpaca API keys not found. Copy .env.example to "
                ".env and fill in ALPACA_API_KEY / ALPACA_SECRET_KEY."
            )

        self.trading_client = TradingClient(
            ALPACA_API_KEY,
            ALPACA_SECRET_KEY,
            paper=True,
        )

        self.data_client = StockHistoricalDataClient(
            ALPACA_API_KEY,
            ALPACA_SECRET_KEY,
        )

    def get_markets(self):
        """Return tradable, fractionable US equity symbols."""

        request = GetAssetsRequest(
            asset_class=AssetClass.US_EQUITY,
            status=AssetStatus.ACTIVE,
        )

        assets = self.trading_client.get_all_assets(request)

        symbols = [
            asset.symbol
            for asset in assets
            if asset.tradable and asset.fractionable
        ]

        symbols.sort()

        return symbols[:STOCK_SCAN_LIMIT]

    def get_ticker(self, symbol):
        """Return the latest trade price, shaped like exchange.get_ticker()."""

        request = StockLatestTradeRequest(
            symbol_or_symbols=symbol,
            feed=DataFeed.IEX,
        )

        trade = self.data_client.get_stock_latest_trade(request)[symbol]

        return {"last": float(trade.price)}

    def get_candles(self, symbol):

        return self.get_historical_candles(
            symbol,
            limit=STOCK_CANDLE_LIMIT,
        )

    def get_historical_candles(self, symbol, since=None, limit=1000):
        """
        Fetch OHLCV bars in ccxt's [ts, open, high, low, close, volume]
        list shape. Stocks only trade ~6.5h/weekday, so the calendar
        padding is generous to make sure enough bars exist in range.

        Alpaca's `limit` truncates from the START of the date range,
        not the end -- so when since is None (the "give me the most
        recent N bars" case, used by the live scanner), the padded
        window can contain far more than `limit` bars and the API's
        own limit would silently return the OLDEST ones, not the most
        recent. Fixed by fetching the whole padded window uncapped and
        slicing the tail client-side. When `since` IS given (backtest
        pagination, walking forward in time), ascending-from-since is
        the correct/intended behaviour, so `limit` is used as-is.
        """

        end = datetime.now(timezone.utc)

        if since is not None:
            start = datetime.fromtimestamp(since / 1000, tz=timezone.utc)
            request_limit = limit
        else:
            bars_per_session = (6.5 * 60) / STOCK_TIMEFRAME_MINUTES
            sessions_needed = (limit / bars_per_session) + 3
            start = end - timedelta(days=sessions_needed * 1.6)
            request_limit = 10000

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame(
                STOCK_TIMEFRAME_MINUTES,
                TimeFrameUnit.Minute,
            ),
            start=start,
            end=end,
            limit=request_limit,
            feed=DataFeed.IEX,
        )

        bar_set = self.data_client.get_stock_bars(request)

        bars = bar_set[symbol] if symbol in bar_set.data else []

        if since is None:
            bars = bars[-limit:]

        return [
            [
                int(bar.timestamp.timestamp() * 1000),
                float(bar.open),
                float(bar.high),
                float(bar.low),
                float(bar.close),
                float(bar.volume),
            ]
            for bar in bars
        ]

    def now_ms(self):

        return int(datetime.now(timezone.utc).timestamp() * 1000)


# Only instantiate once real keys are present -- importing this
# module before .env is filled in will raise, same as exchange.py
# raises without network/exchange access.
exchange = StockExchange()
