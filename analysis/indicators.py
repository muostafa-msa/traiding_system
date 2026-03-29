from __future__ import annotations

import pandas as pd
import ta as ta_lib

from core.logger import get_logger
from core.types import OHLCBar, IndicatorResult

logger = get_logger(__name__)


def compute_indicators(bars: list[OHLCBar]) -> IndicatorResult:
    if len(bars) < 200:
        raise ValueError(
            f"Need at least 200 bars for valid indicators, got {len(bars)}"
        )

    df = pd.DataFrame(
        [
            {
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in bars
        ]
    )

    rsi_series = ta_lib.momentum.RSIIndicator(df["close"], window=14).rsi()
    rsi = float(rsi_series.iloc[-1])

    macd = ta_lib.trend.MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
    macd_line = float(macd.macd().iloc[-1])
    macd_signal = float(macd.macd_signal().iloc[-1])
    macd_hist = float(macd.macd_diff().iloc[-1])

    ema_20 = float(ta_lib.trend.ema_indicator(df["close"], window=20).iloc[-1])
    ema_50 = float(ta_lib.trend.ema_indicator(df["close"], window=50).iloc[-1])
    ema_200 = float(ta_lib.trend.ema_indicator(df["close"], window=200).iloc[-1])

    bb = ta_lib.volatility.BollingerBands(df["close"], window=20, window_dev=2)
    bb_upper = float(bb.bollinger_hband().iloc[-1])
    bb_middle = float(bb.bollinger_mavg().iloc[-1])
    bb_lower = float(bb.bollinger_lband().iloc[-1])

    atr_series = ta_lib.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], window=14
    )
    atr = float(atr_series.average_true_range().iloc[-1])

    support, resistance = _detect_support_resistance(df)

    trend_direction = _detect_trend(df, ema_20, ema_50, ema_200)

    breakout_probability = _estimate_breakout_probability(
        df, bb_upper, bb_middle, bb_lower, atr
    )

    return IndicatorResult(
        rsi=rsi,
        macd_line=macd_line,
        macd_signal=macd_signal,
        macd_hist=macd_hist,
        ema_20=ema_20,
        ema_50=ema_50,
        ema_200=ema_200,
        bb_upper=bb_upper,
        bb_middle=bb_middle,
        bb_lower=bb_lower,
        atr=atr,
        support=support,
        resistance=resistance,
        trend_direction=trend_direction,
        breakout_probability=breakout_probability,
    )


def _detect_support_resistance(
    df: pd.DataFrame, n: int = 5, lookback: int = 50
) -> tuple[float, float]:
    recent = df.tail(lookback)
    highs = recent["high"].values
    lows = recent["low"].values

    support = float(recent["low"].iloc[-1])
    resistance = float(recent["high"].iloc[-1])

    for i in range(n, len(highs) - n):
        is_swing_high = all(
            highs[i] >= highs[i + j] for j in range(-n, n + 1) if j != 0
        )
        if is_swing_high:
            resistance = float(highs[i])

    for i in range(n, len(lows) - n):
        is_swing_low = all(lows[i] <= lows[i + j] for j in range(-n, n + 1) if j != 0)
        if is_swing_low:
            support = float(lows[i])

    return support, resistance


def _detect_trend(
    df: pd.DataFrame, ema_20: float, ema_50: float, ema_200: float
) -> str:
    close = float(df["close"].iloc[-1])

    if close > ema_20 > ema_50 > ema_200:
        return "bullish"
    elif close < ema_20 < ema_50 < ema_200:
        return "bearish"
    else:
        return "neutral"


def _estimate_breakout_probability(
    df: pd.DataFrame,
    bb_upper: float,
    bb_middle: float,
    bb_lower: float,
    atr: float,
) -> float:
    if bb_middle <= 0:
        return 0.5

    bb_width = (bb_upper - bb_lower) / bb_middle
    close = float(df["close"].iloc[-1])

    atr_series = ta_lib.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], window=14
    )
    atr_values = atr_series.average_true_range().dropna()

    if len(atr_values) < 20:
        return 0.5

    atr_mean = float(atr_values.tail(20).mean())
    if atr_mean <= 0:
        return 0.5

    volatility_ratio = atr / atr_mean

    squeeze_factor = min(bb_width / 0.02, 1.0)
    vol_factor = min(volatility_ratio / 2.0, 1.0)

    bb_position = 0.5
    if (bb_upper - bb_lower) > 0:
        bb_position = (close - bb_lower) / (bb_upper - bb_lower)

    near_band_boost = 0.0
    if bb_position > 0.85 or bb_position < 0.15:
        near_band_boost = 0.1

    raw = (1.0 - squeeze_factor) * 0.4 + vol_factor * 0.4 + near_band_boost + 0.1
    probability = max(0.0, min(1.0, raw))

    return probability
