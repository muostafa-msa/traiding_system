from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from agents.chart_agent import (
    ChartAgent,
    compute_clarity_score,
    compute_data_completeness,
    compute_indicator_agreement,
)
from core.config import AppConfig
from core.types import (
    ClarityScore,
    IndicatorResult,
    OHLCBar,
    PatternDetectionResult,
    PatternResult,
    TimeframeAnalysis,
)


def _make_bars(count: int, start_price: float = 2300.0) -> list[OHLCBar]:
    bars = []
    base = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    for i in range(count):
        hour = i // 60
        minute = i % 60
        ts = base.replace(hour=hour % 24, minute=minute)
        bars.append(
            OHLCBar(
                timestamp=ts,
                open=start_price + i * 0.5,
                high=start_price + i * 0.5 + 2.0,
                low=start_price + i * 0.5 - 2.0,
                close=start_price + i * 0.5 + 1.0,
                volume=1000.0,
            )
        )
    return bars


def _bullish_indicators() -> IndicatorResult:
    return IndicatorResult(
        rsi=65.0,
        macd_line=2.0,
        macd_signal=1.5,
        macd_hist=0.5,
        ema_20=2350.0,
        ema_50=2340.0,
        ema_200=2320.0,
        bb_upper=2360.0,
        bb_middle=2350.0,
        bb_lower=2340.0,
        atr=15.0,
        support=2340.0,
        resistance=2360.0,
        trend_direction="bullish",
        breakout_probability=0.4,
    )


def _bearish_indicators() -> IndicatorResult:
    return IndicatorResult(
        rsi=35.0,
        macd_line=-2.0,
        macd_signal=-1.5,
        macd_hist=-0.5,
        ema_20=2300.0,
        ema_50=2310.0,
        ema_200=2320.0,
        bb_upper=2330.0,
        bb_middle=2305.0,
        bb_lower=2280.0,
        atr=15.0,
        support=2290.0,
        resistance=2310.0,
        trend_direction="bearish",
        breakout_probability=0.3,
    )


def _neutral_indicators() -> IndicatorResult:
    return IndicatorResult(
        rsi=50.0,
        macd_line=0.0,
        macd_signal=0.0,
        macd_hist=0.0,
        ema_20=2320.0,
        ema_50=2320.0,
        ema_200=2320.0,
        bb_upper=2320.0,
        bb_middle=2320.0,
        bb_lower=2320.0,
        atr=15.0,
        support=2310.0,
        resistance=2330.0,
        trend_direction="neutral",
        breakout_probability=0.1,
    )


def _neutral_patterns() -> PatternDetectionResult:
    return PatternDetectionResult(
        patterns=[],
        strongest_confidence=0.0,
        strongest_direction="NEUTRAL",
    )


def _strong_bullish_pattern() -> PatternDetectionResult:
    return PatternDetectionResult(
        patterns=[
            PatternResult(
                pattern_type="breakout",
                confidence=0.85,
                direction="BUY",
                price_level=2360.0,
            )
        ],
        strongest_confidence=0.85,
        strongest_direction="BUY",
    )


class TestComputeIndicatorAgreement:
    def test_all_bullish(self):
        indicators = _bullish_indicators()
        agreement = compute_indicator_agreement(indicators)
        assert agreement == 1.0

    def test_all_bearish(self):
        indicators = _bearish_indicators()
        agreement = compute_indicator_agreement(indicators)
        assert agreement == 1.0

    def test_all_neutral(self):
        indicators = _neutral_indicators()
        agreement = compute_indicator_agreement(indicators)
        assert agreement == 0.0

    def test_partial_agreement(self):
        indicators = IndicatorResult(
            rsi=65.0,
            macd_line=0.0,
            macd_signal=0.0,
            macd_hist=0.0,
            ema_20=2350.0,
            ema_50=2340.0,
            ema_200=2320.0,
            bb_upper=2360.0,
            bb_middle=2340.0,
            bb_lower=2320.0,
            atr=15.0,
            support=2340.0,
            resistance=2360.0,
            trend_direction="bullish",
            breakout_probability=0.4,
        )
        agreement = compute_indicator_agreement(indicators)
        assert agreement == 0.5

    def test_returns_float_rounded(self):
        indicators = _bullish_indicators()
        result = compute_indicator_agreement(indicators)
        assert isinstance(result, float)
        decimals = str(result).split(".")[-1] if "." in str(result) else "0"
        assert len(decimals) <= 4


class TestComputeDataCompleteness:
    def test_full_data(self):
        bars = _make_bars(250)
        result = compute_data_completeness(bars, expected_count=250)
        assert result == 1.0

    def test_half_data(self):
        bars = _make_bars(125)
        result = compute_data_completeness(bars, expected_count=250)
        assert result == 0.5

    def test_no_bars(self):
        result = compute_data_completeness([], expected_count=250)
        assert result == 0.0

    def test_excess_bars_capped(self):
        bars = _make_bars(300)
        result = compute_data_completeness(bars, expected_count=250)
        assert result == 1.0

    def test_zero_expected(self):
        bars = _make_bars(50)
        result = compute_data_completeness(bars, expected_count=0)
        assert result == 1.0


class TestComputeClarityScore:
    def test_composite_formula(self):
        indicators = _bullish_indicators()
        patterns = _strong_bullish_pattern()
        bars = _make_bars(250)
        score = compute_clarity_score("1h", indicators, patterns, bars)
        expected = 0.5 * 1.0 + 0.3 * 0.85 + 0.2 * 1.0
        assert abs(score.composite - expected) < 0.01

    def test_low_composite_with_no_patterns_and_sparse_data(self):
        indicators = _neutral_indicators()
        patterns = _neutral_patterns()
        bars = _make_bars(50)
        score = compute_clarity_score(
            "1h", indicators, patterns, bars, expected_bars=250
        )
        expected = 0.5 * 0.0 + 0.3 * 0.0 + 0.2 * (50 / 250)
        assert abs(score.composite - expected) < 0.01

    def test_fields_populated(self):
        indicators = _bullish_indicators()
        patterns = _neutral_patterns()
        bars = _make_bars(200)
        score = compute_clarity_score("15m", indicators, patterns, bars)
        assert score.timeframe == "15m"
        assert score.indicator_agreement == 1.0
        assert score.pattern_confidence == 0.0
        assert score.data_completeness == 0.8

    def test_composite_in_valid_range(self):
        indicators = _bullish_indicators()
        patterns = _strong_bullish_pattern()
        bars = _make_bars(250)
        score = compute_clarity_score("4h", indicators, patterns, bars)
        assert 0.0 <= score.composite <= 1.0


class TestChartAgentAnalyze:
    def test_analyze_returns_timeframe_analysis(self):
        agent = ChartAgent()
        bars = _make_bars(250)
        with (
            patch("agents.chart_agent.compute_indicators") as mock_ind,
            patch("agents.chart_agent.detect_patterns") as mock_pat,
        ):
            mock_ind.return_value = _bullish_indicators()
            mock_pat.return_value = _neutral_patterns()
            result = agent.analyze(bars, "1h")

        assert isinstance(result, TimeframeAnalysis)
        assert result.timeframe == "1h"
        assert isinstance(result.clarity, ClarityScore)
        assert result.bars is bars

    def test_analyze_stores_in_internal_cache(self):
        agent = ChartAgent()
        bars = _make_bars(250)
        with (
            patch("agents.chart_agent.compute_indicators") as mock_ind,
            patch("agents.chart_agent.detect_patterns") as mock_pat,
        ):
            mock_ind.return_value = _bullish_indicators()
            mock_pat.return_value = _neutral_patterns()
            agent.analyze(bars, "1h")

        assert "1h" in agent._analyses

    def test_analyze_raises_on_insufficient_bars(self):
        agent = ChartAgent()
        bars = _make_bars(50)
        with pytest.raises(ValueError, match="Need at least 200 bars"):
            agent.analyze(bars, "1h")

    def test_analyze_passes_indicators_to_pattern_detection(self):
        agent = ChartAgent()
        bars = _make_bars(250)
        indicators = _bullish_indicators()
        with (
            patch("agents.chart_agent.compute_indicators") as mock_ind,
            patch("agents.chart_agent.detect_patterns") as mock_pat,
        ):
            mock_ind.return_value = indicators
            mock_pat.return_value = _neutral_patterns()
            agent.analyze(bars, "1h")

        mock_pat.assert_called_once_with(
            bars,
            support=indicators.support,
            resistance=indicators.resistance,
            atr=indicators.atr,
        )


class TestChartAgentSelectBestTimeframe:
    def test_selects_highest_composite(self):
        agent = ChartAgent()
        analyses = [
            TimeframeAnalysis(
                timeframe="5m",
                indicators=_neutral_indicators(),
                patterns=_neutral_patterns(),
                clarity=ClarityScore(
                    timeframe="5m",
                    indicator_agreement=0.25,
                    pattern_confidence=0.0,
                    data_completeness=0.8,
                ),
                bars=_make_bars(200),
                timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            ),
            TimeframeAnalysis(
                timeframe="1h",
                indicators=_bullish_indicators(),
                patterns=_strong_bullish_pattern(),
                clarity=ClarityScore(
                    timeframe="1h",
                    indicator_agreement=1.0,
                    pattern_confidence=0.85,
                    data_completeness=1.0,
                ),
                bars=_make_bars(250),
                timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            ),
        ]
        best = agent.select_best_timeframe(analyses)
        assert best.timeframe == "1h"

    def test_single_analysis_returns_it(self):
        agent = ChartAgent()
        analysis = TimeframeAnalysis(
            timeframe="4h",
            indicators=_neutral_indicators(),
            patterns=_neutral_patterns(),
            clarity=ClarityScore(
                timeframe="4h",
                indicator_agreement=0.0,
                pattern_confidence=0.0,
                data_completeness=0.5,
            ),
            bars=_make_bars(125),
            timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        )
        result = agent.select_best_timeframe([analysis])
        assert result.timeframe == "4h"

    def test_uses_internal_cache_when_no_args(self):
        agent = ChartAgent()
        bars = _make_bars(250)
        with (
            patch("agents.chart_agent.compute_indicators") as mock_ind,
            patch("agents.chart_agent.detect_patterns") as mock_pat,
        ):
            mock_ind.return_value = _bullish_indicators()
            mock_pat.return_value = _neutral_patterns()
            agent.analyze(bars, "1h")

        best = agent.select_best_timeframe()
        assert best.timeframe == "1h"

    def test_raises_on_empty_analyses(self):
        agent = ChartAgent()
        with pytest.raises(ValueError, match="No analyses available"):
            agent.select_best_timeframe([])

    def test_raises_on_no_cache_and_no_args(self):
        agent = ChartAgent()
        with pytest.raises(ValueError, match="No analyses available"):
            agent.select_best_timeframe()


class TestDataCompletenessPenalty:
    def test_sparse_data_reduces_composite(self):
        full_bars = _make_bars(250)
        sparse_bars = _make_bars(50)

        score_full = compute_clarity_score(
            "1h", _neutral_indicators(), _neutral_patterns(), full_bars
        )
        score_sparse = compute_clarity_score(
            "1h", _neutral_indicators(), _neutral_patterns(), sparse_bars
        )
        assert score_sparse.composite < score_full.composite

    def test_completeness_weight_is_20_percent(self):
        bars = _make_bars(0 + 1)
        indicators = _neutral_indicators()
        patterns = _neutral_patterns()
        score = compute_clarity_score(
            "1h", indicators, patterns, bars, expected_bars=250
        )
        completeness_contribution = 0.2 * (1 / 250)
        assert abs(score.composite - completeness_contribution) < 0.001


from unittest.mock import MagicMock, patch

from execution.telegram_bot import TelegramBot
from storage.database import Database
from tests.conftest import _default_sentiment_fields


def _make_scheduler(config: AppConfig, chart_agent: ChartAgent):
    from core.scheduler import TradingScheduler

    with patch("core.scheduler.get_provider") as mock_get_prov:
        provider = MagicMock()
        provider.get_ohlc.return_value = []
        mock_get_prov.return_value = provider
        db = Database(config)
        bot = MagicMock(spec=TelegramBot)
        scheduler = TradingScheduler(config, db, bot)
    scheduler._chart_agent = chart_agent
    return scheduler


class TestMTFConfirmation:
    def _make_analysis(self, timeframe: str, trend_direction: str) -> TimeframeAnalysis:
        if trend_direction == "bullish":
            indicators = _bullish_indicators()
        elif trend_direction == "bearish":
            indicators = _bearish_indicators()
        else:
            indicators = _neutral_indicators()
        return TimeframeAnalysis(
            timeframe=timeframe,
            indicators=indicators,
            patterns=_neutral_patterns(),
            clarity=ClarityScore(
                timeframe=timeframe,
                indicator_agreement=0.5,
                pattern_confidence=0.0,
                data_completeness=1.0,
            ),
            bars=_make_bars(250),
            timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        )

    def test_get_trend_consensus_empty(self):
        agent = ChartAgent()
        result = agent.get_trend_consensus("1h")
        assert result == {"total": 0, "bullish": 0, "bearish": 0, "neutral": 0}

    def test_get_trend_consensus_partial(self):
        agent = ChartAgent()
        agent._analyses["5m"] = self._make_analysis("5m", "bullish")
        agent._analyses["1h"] = self._make_analysis("1h", "bearish")
        result = agent.get_trend_consensus("1h")
        assert result == {"total": 1, "bullish": 1, "bearish": 0, "neutral": 0}

    def test_get_trend_consensus_full(self):
        agent = ChartAgent()
        agent._analyses["5m"] = self._make_analysis("5m", "bullish")
        agent._analyses["15m"] = self._make_analysis("15m", "bullish")
        agent._analyses["1h"] = self._make_analysis("1h", "bearish")
        agent._analyses["4h"] = self._make_analysis("4h", "neutral")
        result = agent.get_trend_consensus("1h")
        assert result["total"] == 3
        assert result["bullish"] == 2
        assert result["bearish"] == 0
        assert result["neutral"] == 1

    def test_cold_start_allows_through(self, test_config):
        agent = ChartAgent()
        agent._analyses["1h"] = self._make_analysis("1h", "bullish")
        scheduler = _make_scheduler(test_config, agent)
        assert scheduler._check_mtf_agreement("BUY", agent._analyses["1h"]) is True

    def test_rejection_insufficient_agreement(self, test_config):
        agent = ChartAgent()
        agent._analyses["5m"] = self._make_analysis("5m", "bearish")
        agent._analyses["15m"] = self._make_analysis("15m", "bearish")
        agent._analyses["1h"] = self._make_analysis("1h", "bullish")
        agent._analyses["4h"] = self._make_analysis("4h", "neutral")
        scheduler = _make_scheduler(test_config, agent)
        result = scheduler._check_mtf_agreement("BUY", agent._analyses["1h"])
        assert result is False

    def test_passes_with_sufficient_agreement(self, test_config):
        agent = ChartAgent()
        agent._analyses["5m"] = self._make_analysis("5m", "bullish")
        agent._analyses["15m"] = self._make_analysis("15m", "bullish")
        agent._analyses["1h"] = self._make_analysis("1h", "bullish")
        agent._analyses["4h"] = self._make_analysis("4h", "bearish")
        scheduler = _make_scheduler(test_config, agent)
        result = scheduler._check_mtf_agreement("BUY", agent._analyses["1h"])
        assert result is True

    def test_disabled_allows_through(self, test_config):
        from dataclasses import replace

        config = replace(test_config, mtf_confirmation_enabled=False)
        agent = ChartAgent()
        agent._analyses["5m"] = self._make_analysis("5m", "bearish")
        agent._analyses["1h"] = self._make_analysis("1h", "bullish")
        scheduler = _make_scheduler(config, agent)
        assert scheduler._check_mtf_agreement("BUY", agent._analyses["1h"]) is True
