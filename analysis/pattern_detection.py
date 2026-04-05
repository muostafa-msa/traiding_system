from __future__ import annotations

from core.logger import get_logger
from core.types import OHLCBar, PatternDetectionResult, PatternResult

logger = get_logger(__name__)

MIN_BARS = 50
SWING_N = 5


def detect_breakout(
    bars: list[OHLCBar], support: float, resistance: float, atr: float
) -> PatternResult | None:
    if len(bars) < MIN_BARS or atr <= 0:
        return None

    close = bars[-1].close
    prev_close = bars[-2].close if len(bars) >= 2 else close

    if close > resistance:
        magnitude = (close - resistance) / atr
        confidence = min(magnitude / 2.0, 1.0)
        confidence = max(0.3, confidence)
        return PatternResult(
            pattern_type="breakout",
            confidence=round(confidence, 4),
            direction="BUY",
            price_level=close,
        )

    if close < support:
        magnitude = (support - close) / atr
        confidence = min(magnitude / 2.0, 1.0)
        confidence = max(0.3, confidence)
        return PatternResult(
            pattern_type="breakout",
            confidence=round(confidence, 4),
            direction="SELL",
            price_level=close,
        )

    return None


def detect_triangle(bars: list[OHLCBar]) -> PatternResult | None:
    if len(bars) < MIN_BARS + 10:
        return None

    lookback = bars[-(MIN_BARS):]
    highs = [b.high for b in lookback]
    lows = [b.low for b in lookback]
    n = len(lookback)

    swing_highs = _find_swing_highs(highs)
    swing_lows = _find_swing_lows(lows)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return None

    high_idx_start, high_val_start = swing_highs[0]
    high_idx_end, high_val_end = swing_highs[-1]
    low_idx_start, low_val_start = swing_lows[0]
    low_idx_end, low_val_end = swing_lows[-1]

    high_slope = (high_val_end - high_val_start) / max(high_idx_end - high_idx_start, 1)
    low_slope = (low_val_end - low_val_start) / max(low_idx_end - low_idx_start, 1)

    if high_slope >= 0 or low_slope <= 0:
        return None

    total_swing_touches = len(swing_highs) + len(swing_lows)
    touch_score = min(total_swing_touches / 8.0, 1.0)

    high_range = abs(high_val_start - high_val_end)
    low_range = abs(low_val_start - low_val_end)
    price_range = max(high_val_start - low_val_start, 0.001)
    convergence = 1.0 - (high_range + low_range) / (2.0 * price_range)
    convergence = max(0.0, min(1.0, convergence))

    confidence = 0.4 * touch_score + 0.6 * convergence
    if confidence < 0.2:
        return None

    close = lookback[-1].close
    mid_point = (high_val_start + low_val_start) / 2.0
    direction = "BUY" if close > mid_point else "SELL"

    return PatternResult(
        pattern_type="triangle",
        confidence=round(confidence, 4),
        direction=direction,
        price_level=close,
    )


def detect_double_top(bars: list[OHLCBar]) -> PatternResult | None:
    if len(bars) < MIN_BARS:
        return None

    lookback = bars[-60:] if len(bars) >= 60 else bars
    highs = [b.high for b in lookback]
    n = len(highs)

    swing_highs = _find_swing_highs(highs)
    if len(swing_highs) < 2:
        return None

    for i in range(len(swing_highs)):
        for j in range(i + 1, len(swing_highs)):
            idx1, val1 = swing_highs[i]
            idx2, val2 = swing_highs[j]

            separation = abs(idx2 - idx1)
            if separation < 10:
                continue

            price_diff = abs(val1 - val2) / max(val1, val2, 0.001)
            if price_diff > 0.02:
                continue

            symmetry = 1.0 - price_diff / 0.02
            confidence = 0.5 + 0.5 * symmetry

            return PatternResult(
                pattern_type="double_top",
                confidence=round(confidence, 4),
                direction="SELL",
                price_level=max(val1, val2),
            )

    return None


def detect_double_bottom(bars: list[OHLCBar]) -> PatternResult | None:
    if len(bars) < MIN_BARS:
        return None

    lookback = bars[-60:] if len(bars) >= 60 else bars
    lows = [b.low for b in lookback]

    swing_lows = _find_swing_lows(lows)
    if len(swing_lows) < 2:
        return None

    for i in range(len(swing_lows)):
        for j in range(i + 1, len(swing_lows)):
            idx1, val1 = swing_lows[i]
            idx2, val2 = swing_lows[j]

            separation = abs(idx2 - idx1)
            if separation < 10:
                continue

            price_diff = abs(val1 - val2) / max(val1, val2, 0.001)
            if price_diff > 0.02:
                continue

            symmetry = 1.0 - price_diff / 0.02
            confidence = 0.5 + 0.5 * symmetry

            return PatternResult(
                pattern_type="double_bottom",
                confidence=round(confidence, 4),
                direction="BUY",
                price_level=min(val1, val2),
            )

    return None


def detect_head_shoulders(bars: list[OHLCBar]) -> PatternResult | None:
    if len(bars) < MIN_BARS:
        return None

    lookback = bars[-80:] if len(bars) >= 80 else bars
    highs = [b.high for b in lookback]
    lows = [b.low for b in lookback]

    swing_highs = _find_swing_highs(highs)
    if len(swing_highs) < 3:
        return None

    for i in range(len(swing_highs) - 2):
        ls_idx, ls_val = swing_highs[i]
        head_idx, head_val = swing_highs[i + 1]
        rs_idx, rs_val = swing_highs[i + 2]

        if head_val <= ls_val or head_val <= rs_val:
            continue

        neckline = min(ls_val, rs_val)
        close = lookback[-1].close

        shoulder_diff = abs(ls_val - rs_val) / head_val
        symmetry = max(0.0, 1.0 - shoulder_diff / 0.03)
        symmetry = min(1.0, symmetry)

        neckline_break = 0.0
        if head_val > neckline:
            penetration = (neckline - close) / (head_val - neckline)
            neckline_break = max(0.0, min(1.0, penetration))

        confidence = 0.4 * symmetry + 0.6 * neckline_break
        if confidence < 0.2:
            continue

        return PatternResult(
            pattern_type="head_shoulders",
            confidence=round(confidence, 4),
            direction="SELL",
            price_level=close,
        )

    return None


def detect_range(
    bars: list[OHLCBar], support: float, resistance: float
) -> PatternResult | None:
    if len(bars) < MIN_BARS:
        return None

    lookback = bars[-50:] if len(bars) >= 50 else bars
    if support <= 0 or resistance <= 0 or resistance <= support:
        return None

    range_size = resistance - support
    if range_size <= 0:
        return None

    touch_count = 0
    for bar in lookback:
        near_resistance = abs(bar.high - resistance) / range_size < 0.05
        near_support = abs(bar.low - support) / range_size < 0.05
        if near_resistance or near_support:
            touch_count += 1

    if touch_count < 4:
        return None

    touch_score = min(touch_count / 10.0, 1.0)

    mid = (support + resistance) / 2.0
    deviations = [abs(b.close - mid) / range_size for b in lookback]
    avg_deviation = sum(deviations) / len(deviations)
    tightness = max(0.0, 1.0 - avg_deviation * 2.0)

    confidence = 0.5 * touch_score + 0.5 * tightness
    if confidence < 0.2:
        return None

    close = lookback[-1].close
    if close > mid:
        direction = "SELL"
    elif close < mid:
        direction = "BUY"
    else:
        direction = "NEUTRAL"

    return PatternResult(
        pattern_type="range",
        confidence=round(confidence, 4),
        direction=direction,
        price_level=close,
    )


def detect_patterns(
    bars: list[OHLCBar],
    support: float | None = None,
    resistance: float | None = None,
    atr: float | None = None,
) -> PatternDetectionResult:
    if len(bars) < MIN_BARS:
        return PatternDetectionResult(
            patterns=[], strongest_confidence=0.0, strongest_direction="NEUTRAL"
        )

    if support is None:
        support = min(b.low for b in bars[-50:])
    if resistance is None:
        resistance = max(b.high for b in bars[-50:])
    if atr is None:
        atr = _compute_atr(bars)

    results: list[PatternResult] = []

    breakout = detect_breakout(bars, support, resistance, atr)
    if breakout is not None:
        results.append(breakout)

    triangle = detect_triangle(bars)
    if triangle is not None:
        results.append(triangle)

    dt = detect_double_top(bars)
    if dt is not None:
        results.append(dt)

    db = detect_double_bottom(bars)
    if db is not None:
        results.append(db)

    hs = detect_head_shoulders(bars)
    if hs is not None:
        results.append(hs)

    rng = detect_range(bars, support, resistance)
    if rng is not None:
        results.append(rng)

    if not results:
        return PatternDetectionResult(
            patterns=[], strongest_confidence=0.0, strongest_direction="NEUTRAL"
        )

    best = max(results, key=lambda p: p.confidence)
    return PatternDetectionResult(
        patterns=results,
        strongest_confidence=best.confidence,
        strongest_direction=best.direction,
    )


def _find_swing_highs(highs: list[float], n: int = SWING_N) -> list[tuple[int, float]]:
    swings = []
    for i in range(n, len(highs) - n):
        is_swing = all(highs[i] >= highs[i + j] for j in range(-n, n + 1) if j != 0)
        if is_swing:
            swings.append((i, highs[i]))
    return swings


def _find_swing_lows(lows: list[float], n: int = SWING_N) -> list[tuple[int, float]]:
    swings = []
    for i in range(n, len(lows) - n):
        is_swing = all(lows[i] <= lows[i + j] for j in range(-n, n + 1) if j != 0)
        if is_swing:
            swings.append((i, lows[i]))
    return swings


def _compute_atr(bars: list[OHLCBar], period: int = 14) -> float:
    if len(bars) < period + 1:
        return 0.0
    true_ranges = []
    for i in range(-period, 0):
        high = bars[i].high
        low = bars[i].low
        prev_close = bars[i - 1].close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
    return sum(true_ranges) / len(true_ranges)
