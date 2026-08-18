"""
=========================================
ATLAS AI
Indicators Engine
=========================================
"""

import pandas as pd

from config import (
    EMA_FAST,
    EMA_SLOW,
    RSI_PERIOD,
    MACD_FAST,
    MACD_SLOW,
    MACD_SIGNAL,
    VOLUME_PERIOD,
    ATR_PERIOD
)


class Indicators:

    @staticmethod
    def ema(closes, period=EMA_FAST):

        closes = pd.Series(closes)

        return closes.ewm(
            span=period,
            adjust=False
        ).mean().iloc[-1]

    @staticmethod
    def ema_fast(closes):

        return Indicators.ema(
            closes,
            EMA_FAST
        )

    @staticmethod
    def ema_slow(closes):

        return Indicators.ema(
            closes,
            EMA_SLOW
        )

    @staticmethod
    def rsi(closes):

        closes = pd.Series(closes)

        delta = closes.diff()

        gain = delta.clip(lower=0)

        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(
            RSI_PERIOD
        ).mean()

        avg_loss = loss.rolling(
            RSI_PERIOD
        ).mean()

        rs = avg_gain / avg_loss

        rsi = 100 - (
            100 / (1 + rs)
        )

        return rsi.iloc[-1]

    @staticmethod
    def macd(closes):

        closes = pd.Series(closes)

        ema_fast = closes.ewm(
            span=MACD_FAST,
            adjust=False
        ).mean()

        ema_slow = closes.ewm(
            span=MACD_SLOW,
            adjust=False
        ).mean()

        macd = ema_fast - ema_slow

        signal = macd.ewm(
            span=MACD_SIGNAL,
            adjust=False
        ).mean()

        histogram = macd - signal

        return (
            macd.iloc[-1],
            signal.iloc[-1],
            histogram.iloc[-1]
        )

    @staticmethod
    def volume_ratio(volumes, period=VOLUME_PERIOD):

        volumes = pd.Series(volumes)

        if len(volumes) < period + 1:
            return 1.0

        baseline = volumes.iloc[-(period + 1):-1].mean()

        if baseline == 0 or pd.isna(baseline):
            return 1.0

        current = volumes.iloc[-1]

        return current / baseline

    @staticmethod
    def atr(highs, lows, closes, period=ATR_PERIOD):

        highs = pd.Series(highs)
        lows = pd.Series(lows)
        closes = pd.Series(closes)

        prev_close = closes.shift(1)

        true_range = pd.concat([
            highs - lows,
            (highs - prev_close).abs(),
            (lows - prev_close).abs(),
        ], axis=1).max(axis=1)

        return true_range.rolling(period).mean().iloc[-1]