from __future__ import annotations

from datetime import datetime, timezone

import pytest

from analysis.pattern_detection import (
    _filter_contradictory_patterns,
    detect_breakout,
    detect_double_bottom,
    detect_double_top,
    detect_head_shoulders,
    detect_patterns,
    detect_range,
    detect_triangle,
)
from core.types import OHLCBar, PatternDetectionResult, PatternResult


def _make_bar(
    price: float,
    spread: float = 2.0,
    volume: float = 1000.0,
    idx: int = 0,
) -> OHLCBar:
    hour = idx // 60
    minute = idx % 60
    return OHLCBar(
        timestamp=datetime(2026, 1, 1, hour, minute, tzinfo=timezone.utc),
        open=price - spread / 2,
        high=price + spread,
        low=price - spread,
        close=price,
        volume=volume,
    )


def _flat_bars(count: int = 60, price: float = 2300.0) -> list[OHLCBar]:
    return [_make_bar(price, idx=i) for i in range(count)]


def _uptrend_bars(count: int = 60, start: float = 2300.0) -> list[OHLCBar]:
    return [_make_bar(start + i * 1.0, idx=i) for i in range(count)]


def _make_breakout_bars(
    count: int = 60, resistance: float = 2350.0, breakout_price: float = 2355.0
) -> list[OHLCBar]:
    bars = []
    for i in range(count - 1):
        bars.append(_make_bar(resistance - 5.0 + (i % 10), idx=i))
    bars.append(_make_bar(breakout_price, idx=count - 1))
    return bars


def _make_triangle_bars(count: int = 60) -> list[OHLCBar]:
    bars = []
    base = 2300.0
    half_period = 6
    for i in range(count):
        t = i / count
        upper_amp = 20.0 * (1.0 - t * 0.7)
        lower_amp = 15.0 * (1.0 - t * 0.6)
        pos = i % (2 * half_period)
        if pos < half_period:
            frac = pos / half_period
            price = base - lower_amp + (upper_amp + lower_amp) * frac
        else:
            frac = (pos - half_period) / half_period
            price = base + upper_amp - (upper_amp + lower_amp) * frac
        bars.append(
            OHLCBar(
                timestamp=datetime(2026, 1, 1, i // 60, i % 60, tzinfo=timezone.utc),
                open=price - 0.5,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=1000.0,
            )
        )
    return bars


def _make_double_top_bars(count: int = 60, peak_price: float = 2350.0) -> list[OHLCBar]:
    bars = []
    for i in range(count):
        if 15 <= i <= 20:
            price = peak_price - (abs(i - 17) * 5.0)
        elif 35 <= i <= 40:
            price = peak_price - (abs(i - 37) * 5.0)
        else:
            price = 2320.0
        bars.append(_make_bar(price, idx=i))
    return bars


def _make_double_bottom_bars(
    count: int = 60, trough_price: float = 2280.0
) -> list[OHLCBar]:
    bars = []
    for i in range(count):
        if 15 <= i <= 20:
            price = trough_price + (abs(i - 17) * 5.0)
        elif 35 <= i <= 40:
            price = trough_price + (abs(i - 37) * 5.0)
        else:
            price = 2320.0
        bars.append(_make_bar(price, idx=i))
    return bars


def _make_head_shoulders_bars(count: int = 80) -> list[OHLCBar]:
    bars = []
    for i in range(count):
        if i == 15:
            price = 2340.0
        elif i == 25:
            price = 2360.0
        elif i == 35:
            price = 2342.0
        elif i < 10 or i > 45:
            price = 2320.0 - max(0, (i - 45) * 2.0)
        else:
            price = 2325.0
        bars.append(_make_bar(price, idx=i))
    return bars


def _make_range_bars(
    count: int = 60, support: float = 2290.0, resistance: float = 2330.0
) -> list[OHLCBar]:
    bars = []
    for i in range(count):
        cycle = (i % 20) / 20.0
        price = support + (resistance - support) * cycle
        bars.append(
            OHLCBar(
                timestamp=datetime(2026, 1, 1, i // 60, i % 60, tzinfo=timezone.utc),
                open=price - 0.5,
                high=price + 1.5,
                low=price - 1.5,
                close=price + 0.5,
                volume=1000.0,
            )
        )
    return bars


class TestDetectBreakout:
    def test_breakout_above_resistance(self):
        bars = _make_breakout_bars(60, resistance=2350.0, breakout_price=2360.0)
        atr = 10.0
        result = detect_breakout(bars, support=2300.0, resistance=2350.0, atr=atr)
        assert result is not None
        assert result.pattern_type == "breakout"
        assert result.direction == "BUY"
        assert 0.0 <= result.confidence <= 1.0
        assert result.price_level == 2360.0

    def test_breakout_below_support(self):
        bars = _flat_bars(59) + [_make_bar(2270.0, idx=59)]
        result = detect_breakout(bars, support=2290.0, resistance=2310.0, atr=10.0)
        assert result is not None
        assert result.direction == "SELL"

    def test_no_breakout_when_price_in_range(self):
        bars = _flat_bars(60, price=2300.0)
        result = detect_breakout(bars, support=2290.0, resistance=2310.0, atr=10.0)
        assert result is None

    def test_confidence_increases_with_magnitude(self):
        bars_small = _flat_bars(59) + [_make_bar(2312.0, idx=59)]
        bars_large = _flat_bars(59) + [_make_bar(2330.0, idx=59)]
        r_small = detect_breakout(bars_small, 2290.0, 2310.0, 10.0)
        r_large = detect_breakout(bars_large, 2290.0, 2310.0, 10.0)
        assert r_small is not None
        assert r_large is not None
        assert r_large.confidence >= r_small.confidence

    def test_returns_none_with_too_few_bars(self):
        bars = _flat_bars(30)
        assert detect_breakout(bars, 2290.0, 2310.0, 10.0) is None


class TestDetectTriangle:
    def test_detects_converging_pattern(self):
        bars = _make_triangle_bars(60)
        result = detect_triangle(bars)
        assert result is not None
        assert result.pattern_type == "triangle"
        assert 0.0 <= result.confidence <= 1.0

    def test_no_triangle_in_flat_market(self):
        bars = _flat_bars(60)
        result = detect_triangle(bars)
        assert result is None

    def test_returns_none_with_too_few_bars(self):
        bars = _flat_bars(40)
        assert detect_triangle(bars) is None


class TestDetectDoubleTop:
    def test_detects_two_similar_peaks(self):
        bars = _make_double_top_bars(60, peak_price=2350.0)
        result = detect_double_top(bars)
        assert result is not None
        assert result.pattern_type == "double_top"
        assert result.direction == "SELL"
        assert 0.0 <= result.confidence <= 1.0

    def test_no_double_top_in_uptrend(self):
        bars = _uptrend_bars(60)
        result = detect_double_top(bars)
        assert result is None

    def test_returns_none_with_too_few_bars(self):
        assert detect_double_top(_flat_bars(30)) is None


class TestDetectDoubleBottom:
    def test_detects_two_similar_troughs(self):
        bars = _make_double_bottom_bars(60, trough_price=2280.0)
        result = detect_double_bottom(bars)
        assert result is not None
        assert result.pattern_type == "double_bottom"
        assert result.direction == "BUY"
        assert 0.0 <= result.confidence <= 1.0

    def test_no_double_bottom_in_downtrend(self):
        bars = [_make_bar(2300.0 - i * 1.0, idx=i) for i in range(60)]
        result = detect_double_bottom(bars)
        assert result is None


class TestDetectHeadShoulders:
    def test_detects_head_and_shoulders_pattern(self):
        bars = _make_head_shoulders_bars(80)
        result = detect_head_shoulders(bars)
        assert result is not None
        assert result.pattern_type == "head_shoulders"
        assert result.direction == "SELL"
        assert 0.0 <= result.confidence <= 1.0

    def test_no_pattern_in_flat_data(self):
        bars = _flat_bars(80)
        result = detect_head_shoulders(bars)
        assert result is None

    def test_returns_none_with_too_few_bars(self):
        assert detect_head_shoulders(_flat_bars(30)) is None


class TestDetectRange:
    def test_detects_oscillating_range(self):
        support = 2290.0
        resistance = 2330.0
        bars = _make_range_bars(60, support=support, resistance=resistance)
        result = detect_range(bars, support=support, resistance=resistance)
        assert result is not None
        assert result.pattern_type == "range"
        assert 0.0 <= result.confidence <= 1.0

    def test_no_range_in_strong_trend(self):
        bars = [_make_bar(2300.0 + i * 3.0, idx=i) for i in range(60)]
        result = detect_range(bars, support=2290.0, resistance=2480.0)
        assert result is None

    def test_returns_none_with_too_few_bars(self):
        assert detect_range(_flat_bars(30), 2290.0, 2310.0) is None


class TestDetectPatternsAggregator:
    def test_returns_neutral_with_too_few_bars(self):
        bars = _flat_bars(30)
        result = detect_patterns(bars)
        assert result.strongest_confidence == 0.0
        assert result.strongest_direction == "NEUTRAL"
        assert len(result.patterns) == 0

    def test_returns_pattern_detection_result(self):
        bars = _make_breakout_bars(60, resistance=2350.0, breakout_price=2360.0)
        result = detect_patterns(bars, support=2300.0, resistance=2350.0, atr=10.0)
        assert isinstance(result, PatternDetectionResult)
        if result.patterns:
            assert result.strongest_confidence > 0.0
            for p in result.patterns:
                assert 0.0 <= p.confidence <= 1.0
                assert p.pattern_type in (
                    "breakout",
                    "triangle",
                    "double_top",
                    "double_bottom",
                    "head_shoulders",
                    "range",
                )

    def test_empty_flat_data_returns_neutral_or_found(self):
        bars = _flat_bars(60)
        result = detect_patterns(bars)
        assert isinstance(result, PatternDetectionResult)
        for p in result.patterns:
            assert 0.0 <= p.confidence <= 1.0

    def test_detect_patterns_with_default_params(self):
        bars = _make_breakout_bars(60, resistance=2350.0, breakout_price=2360.0)
        result = detect_patterns(bars)
        assert isinstance(result, PatternDetectionResult)

    def test_multiple_patterns_can_be_detected(self):
        bars = _make_breakout_bars(60, resistance=2350.0, breakout_price=2360.0)
        result = detect_patterns(bars, support=2300.0, resistance=2350.0, atr=10.0)
        assert isinstance(result, PatternDetectionResult)
        if len(result.patterns) > 1:
            assert result.strongest_confidence == max(
                p.confidence for p in result.patterns
            )


class TestPatternConfidenceBounds:
    def test_all_detectors_return_confidence_in_range(self):
        bars = _flat_bars(60)
        detectors = [
            lambda: detect_breakout(bars, 2290.0, 2310.0, 10.0),
            lambda: detect_triangle(bars),
            lambda: detect_double_top(bars),
            lambda: detect_double_bottom(bars),
            lambda: detect_head_shoulders(bars),
            lambda: detect_range(bars, 2290.0, 2310.0),
        ]
        for detector in detectors:
            result = detector()
            if result is not None:
                assert 0.0 <= result.confidence <= 1.0, (
                    f"confidence {result.confidence} out of range for {result.pattern_type}"
                )


class TestContradictoryPatternFiltering:
    def test_double_top_and_bottom_only_strongest_kept(self):
        patterns = [
            PatternResult("double_top", 0.8, "SELL", 2350.0),
            PatternResult("double_bottom", 0.6, "BUY", 2280.0),
        ]
        filtered = _filter_contradictory_patterns(patterns)
        directions = {p.direction for p in filtered}
        assert "BUY" not in directions
        assert any(p.direction == "SELL" for p in filtered)

    def test_all_neutral_no_filtering(self):
        patterns = [
            PatternResult("range", 0.7, "NEUTRAL", 2300.0),
            PatternResult("range", 0.5, "NEUTRAL", 2300.0),
        ]
        filtered = _filter_contradictory_patterns(patterns)
        assert len(filtered) == 2

    def test_single_pattern_unchanged(self):
        patterns = [
            PatternResult("breakout", 0.9, "BUY", 2360.0),
        ]
        filtered = _filter_contradictory_patterns(patterns)
        assert len(filtered) == 1
        assert filtered[0].pattern_type == "breakout"

    def test_same_direction_both_preserved(self):
        patterns = [
            PatternResult("breakout", 0.8, "BUY", 2360.0),
            PatternResult("triangle", 0.6, "BUY", 2340.0),
        ]
        filtered = _filter_contradictory_patterns(patterns)
        assert len(filtered) == 2

    def test_neutral_preserved_with_directional(self):
        patterns = [
            PatternResult("double_top", 0.8, "SELL", 2350.0),
            PatternResult("range", 0.5, "NEUTRAL", 2300.0),
        ]
        filtered = _filter_contradictory_patterns(patterns)
        assert len(filtered) == 2
        directions = {p.direction for p in filtered}
        assert directions == {"SELL", "NEUTRAL"}

    def test_empty_list_unchanged(self):
        assert _filter_contradictory_patterns([]) == []
