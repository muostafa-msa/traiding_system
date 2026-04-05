from __future__ import annotations

from datetime import datetime, timezone

from analysis.indicators import compute_indicators
from analysis.pattern_detection import detect_patterns
from core.logger import get_logger
from core.types import (
    ClarityScore,
    IndicatorResult,
    OHLCBar,
    PatternDetectionResult,
    TimeframeAnalysis,
)

logger = get_logger(__name__)


def compute_indicator_agreement(indicators: IndicatorResult) -> float:
    bullish_votes = 0
    bearish_votes = 0
    total = 4

    if indicators.rsi > 50:
        bullish_votes += 1
    elif indicators.rsi < 50:
        bearish_votes += 1

    if indicators.macd_hist > 0:
        bullish_votes += 1
    elif indicators.macd_hist < 0:
        bearish_votes += 1

    if indicators.ema_20 > indicators.ema_50 > indicators.ema_200:
        bullish_votes += 1
    elif indicators.ema_20 < indicators.ema_50 < indicators.ema_200:
        bearish_votes += 1

    if indicators.bb_middle > indicators.ema_50:
        bullish_votes += 1
    elif indicators.bb_middle < indicators.ema_50:
        bearish_votes += 1

    agreement = max(bullish_votes, bearish_votes) / total
    return round(agreement, 4)


def compute_data_completeness(bars: list[OHLCBar], expected_count: int = 250) -> float:
    if expected_count <= 0:
        return 1.0
    ratio = len(bars) / expected_count
    return round(max(0.0, min(1.0, ratio)), 4)


def compute_clarity_score(
    timeframe: str,
    indicators: IndicatorResult,
    patterns: PatternDetectionResult,
    bars: list[OHLCBar],
    expected_bars: int = 250,
) -> ClarityScore:
    indicator_agreement = compute_indicator_agreement(indicators)
    pattern_confidence = patterns.strongest_confidence
    data_completeness = compute_data_completeness(bars, expected_bars)

    return ClarityScore(
        timeframe=timeframe,
        indicator_agreement=indicator_agreement,
        pattern_confidence=pattern_confidence,
        data_completeness=data_completeness,
    )


class ChartAgent:
    def __init__(self):
        self._analyses: dict[str, TimeframeAnalysis] = {}

    def analyze(self, bars: list[OHLCBar], timeframe: str) -> TimeframeAnalysis:
        if len(bars) < 200:
            raise ValueError(
                f"Need at least 200 bars for chart analysis, got {len(bars)}"
            )

        indicators = compute_indicators(bars)
        patterns = detect_patterns(
            bars,
            support=indicators.support,
            resistance=indicators.resistance,
            atr=indicators.atr,
        )
        clarity = compute_clarity_score(timeframe, indicators, patterns, bars)

        analysis = TimeframeAnalysis(
            timeframe=timeframe,
            indicators=indicators,
            patterns=patterns,
            clarity=clarity,
            bars=bars,
            timestamp=datetime.now(timezone.utc),
        )

        self._analyses[timeframe] = analysis
        logger.info(
            "Chart analysis for %s: clarity=%.3f (agreement=%.2f pattern=%.2f completeness=%.2f)",
            timeframe,
            clarity.composite,
            clarity.indicator_agreement,
            clarity.pattern_confidence,
            clarity.data_completeness,
        )

        return analysis

    def select_best_timeframe(
        self, analyses: list[TimeframeAnalysis] | None = None
    ) -> TimeframeAnalysis:
        if analyses is None:
            analyses = list(self._analyses.values())

        if not analyses:
            raise ValueError("No analyses available for timeframe selection")

        if len(analyses) == 1:
            return analyses[0]

        best = max(analyses, key=lambda a: a.clarity.composite)
        logger.info(
            "Selected best timeframe: %s (clarity=%.3f)",
            best.timeframe,
            best.clarity.composite,
        )
        return best
