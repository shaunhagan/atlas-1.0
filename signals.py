"""
=========================================
ATLAS AI
Signal Engine
=========================================
"""

from config import (
    MIN_CONFIDENCE,
    MIN_EMA_SPREAD_PCT,
    MIN_MACD_HIST_PCT,
    MIN_VOLUME_RATIO,
)


class SignalEngine:
    """Convert indicator values into a BUY/HOLD/SELL decision."""

    @staticmethod
    def evaluate(
        price,
        ema_fast,
        ema_slow,
        rsi,
        macd,
        signal,
        histogram,
        volume_ratio,
        min_confidence=MIN_CONFIDENCE,
        min_ema_spread_pct=MIN_EMA_SPREAD_PCT,
        min_macd_hist_pct=MIN_MACD_HIST_PCT,
        min_volume_ratio=MIN_VOLUME_RATIO,
        use_trend=True,
        use_rsi=True,
        use_macd=True,
        # Defaults to False: ablation testing (OPTIMIZATION_LOG.md,
        # 2026-08-18) confirmed on 88 vs 103 held-out test trades
        # that this component actively hurts out-of-sample
        # expectancy (+0.610% with it vs +1.112% without). Kept as
        # a toggle, not deleted, so future research can re-enable
        # it explicitly for comparison.
        use_momentum=False,
        use_volume=True,
        use_chop_gate=True,
    ):
        """
        Return a consistent signal result.

        The confidence score represents bullish conviction:
        higher = more bullish, lower = more bearish.

        Threshold parameters default to the live config values but
        are overridable so the backtester can sweep them without
        touching config.py. The use_* flags default to True (live
        behaviour unchanged) and let the backtester ablate individual
        scoring components to test whether each one actually helps.
        """

        confidence = 0
        reasons = []

        # -----------------------------
        # Trend
        # -----------------------------
        if use_trend:

            if price > ema_fast:
                confidence += 15
                reasons.append("Price above EMA20")
            else:
                confidence -= 10
                reasons.append("Price below EMA20")

            if ema_fast > ema_slow:
                confidence += 20
                reasons.append("EMA20 above EMA50")
            else:
                confidence -= 15
                reasons.append("EMA20 below EMA50")

        # -----------------------------
        # RSI
        # -----------------------------
        if use_rsi:

            if 45 <= rsi <= 60:
                confidence += 15
                reasons.append("Healthy RSI")
            elif 35 <= rsi < 45:
                confidence += 5
                reasons.append("RSI recovering")
            elif rsi < 35:
                confidence += 10
                reasons.append("Oversold")
            elif 60 < rsi <= 70:
                confidence += 5
                reasons.append("Strong RSI")
            elif rsi > 70:
                confidence -= 15
                reasons.append("Overbought")

        # -----------------------------
        # MACD
        # -----------------------------
        if use_macd:

            if macd > signal:
                confidence += 20
                reasons.append("Bullish MACD")
            else:
                confidence -= 10
                reasons.append("Bearish MACD")

        # -----------------------------
        # Momentum
        # -----------------------------
        if use_momentum:

            if histogram > 0:
                confidence += 10
                reasons.append("Positive Momentum")
            else:
                confidence -= 5
                reasons.append("Negative Momentum")

        # -----------------------------
        # Volume
        # -----------------------------
        if use_volume:

            if volume_ratio >= min_volume_ratio:
                confidence += 10
                reasons.append("Above-average volume")
            else:
                confidence -= 10
                reasons.append("Below-average volume")

        # -----------------------------
        # Clamp to 0-100
        # -----------------------------
        confidence = max(0, min(100, confidence))

        # -----------------------------
        # Decision
        # -----------------------------
        if confidence >= min_confidence:
            decision = "BUY"
        elif confidence <= 30:
            decision = "SELL"
        else:
            decision = "HOLD"

        # -----------------------------
        # Trend-strength gate
        #
        # If both the EMA spread and the MACD histogram are too
        # small relative to price, the market is chop rather than
        # trending — refuse to BUY/SELL off noise.
        # -----------------------------
        if use_chop_gate:

            ema_spread_pct = abs(ema_fast - ema_slow) / price * 100
            macd_hist_pct = abs(histogram) / price * 100

            if (
                ema_spread_pct < min_ema_spread_pct
                and macd_hist_pct < min_macd_hist_pct
            ):
                decision = "HOLD"
                reasons.append("No clear trend (choppy market)")

        return {
            "decision": decision,
            "confidence": confidence,
            "reasons": reasons,
        }

    @staticmethod
    def get_signal(
        price,
        ema_fast,
        ema_slow,
        rsi,
        macd,
        signal,
        histogram,
        volume_ratio,
        **kwargs,
    ):
        """Return only the BUY/HOLD/SELL decision."""
        result = SignalEngine.evaluate(
            price,
            ema_fast,
            ema_slow,
            rsi,
            macd,
            signal,
            histogram,
            volume_ratio,
            **kwargs,
        )
        return result["decision"]