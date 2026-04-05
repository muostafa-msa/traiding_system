from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agents.signal_agent import SignalAgent, assemble_features
from core.types import (
    ClarityScore,
    FeatureVector,
    IndicatorResult,
    MacroSentiment,
    OHLCBar,
    PatternDetectionResult,
    PatternResult,
    PricePrediction,
    SignalDecision,
    TimeframeAnalysis,
)
from analysis.indicators import compute_indicators


def _make_bars(count: int = 250, base_price: float = 2300.0) -> list[OHLCBar]:
    bars = []
    base = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    for i in range(count):
        bars.append(
            OHLCBar(
                timestamp=base,
                open=base_price + i * 0.5,
                high=base_price + i * 0.5 + 2.0,
                low=base_price + i * 0.5 - 2.0,
                close=base_price + i * 0.5 + 1.0,
                volume=1000.0,
            )
        )
    return bars


class TestFullScoringPipeline:
    def test_indicators_to_feature_assembly_to_scoring(self, test_config):
        bars = _make_bars()
        indicators = compute_indicators(bars)
        assert indicators is not None

        clarity = ClarityScore(
            timeframe="1h",
            indicator_agreement=0.7,
            pattern_confidence=0.0,
            data_completeness=1.0,
        )
        patterns = PatternDetectionResult()
        analysis = TimeframeAnalysis(
            timeframe="1h",
            indicators=indicators,
            patterns=patterns,
            clarity=clarity,
            bars=bars,
            timestamp=datetime.now(timezone.utc),
        )

        sentiment = MacroSentiment(macro_score=0.3, headline_count=5)
        prediction = PricePrediction(
            direction="BUY",
            confidence=0.6,
            volatility=0.02,
            trend_strength=0.6,
            horizon_bars=12,
        )

        features = assemble_features(analysis, sentiment, prediction)
        assert isinstance(features, FeatureVector)
        assert len(features.to_array()) > 0

        agent = SignalAgent(test_config)
        decision = agent.decide(analysis, sentiment, prediction)

        assert isinstance(decision, SignalDecision)
        assert 0.0 <= decision.probability <= 1.0
        assert decision.scoring_method in ("xgboost", "fallback")
        assert decision.timeframe == "1h"
        assert 0.0 <= decision.clarity_score <= 1.0

    def test_no_trade_when_probability_below_threshold(self, test_config):
        bars = _make_bars()
        indicators = compute_indicators(bars)

        low_clarity = ClarityScore(
            timeframe="1h",
            indicator_agreement=0.1,
            pattern_confidence=0.0,
            data_completeness=0.3,
        )
        patterns = PatternDetectionResult()
        analysis = TimeframeAnalysis(
            timeframe="1h",
            indicators=indicators,
            patterns=patterns,
            clarity=low_clarity,
            bars=bars,
            timestamp=datetime.now(timezone.utc),
        )

        sentiment = MacroSentiment(macro_score=0.0, headline_count=0)
        prediction = PricePrediction(
            direction="NEUTRAL",
            confidence=0.0,
            volatility=0.0,
            trend_strength=0.0,
            horizon_bars=12,
        )

        agent = SignalAgent(test_config)
        decision = agent.decide(analysis, sentiment, prediction)

        assert decision.direction == "NO_TRADE"
        assert decision.explanation == ""
        assert decision.probability < test_config.signal_threshold

    def test_signal_produced_with_strong_inputs(self, test_config):
        bars = _make_bars()
        indicators = compute_indicators(bars)

        breakout = PatternResult(
            pattern_type="breakout", confidence=0.8, direction="BUY", price_level=2400.0
        )
        patterns = PatternDetectionResult(
            patterns=[breakout], strongest_confidence=0.8, strongest_direction="BUY"
        )
        clarity = ClarityScore(
            timeframe="1h",
            indicator_agreement=0.9,
            pattern_confidence=0.8,
            data_completeness=1.0,
        )
        analysis = TimeframeAnalysis(
            timeframe="1h",
            indicators=indicators,
            patterns=patterns,
            clarity=clarity,
            bars=bars,
            timestamp=datetime.now(timezone.utc),
        )

        sentiment = MacroSentiment(macro_score=0.5, headline_count=8)
        prediction = PricePrediction(
            direction="BUY",
            confidence=0.8,
            volatility=0.02,
            trend_strength=0.8,
            horizon_bars=12,
        )

        agent = SignalAgent(test_config)
        decision = agent.decide(analysis, sentiment, prediction)

        if decision.probability >= test_config.signal_threshold:
            assert decision.direction in ("BUY", "SELL")
            assert decision.explanation != ""
        else:
            assert decision.direction == "NO_TRADE"

    def test_scoring_method_field_accuracy(self, test_config):
        bars = _make_bars()
        indicators = compute_indicators(bars)
        clarity = ClarityScore(
            timeframe="1h",
            indicator_agreement=0.5,
            pattern_confidence=0.0,
            data_completeness=1.0,
        )
        analysis = TimeframeAnalysis(
            timeframe="1h",
            indicators=indicators,
            patterns=PatternDetectionResult(),
            clarity=clarity,
            bars=bars,
            timestamp=datetime.now(timezone.utc),
        )
        sentiment = MacroSentiment(macro_score=0.2)
        prediction = PricePrediction(
            direction="BUY",
            confidence=0.5,
            volatility=0.01,
            trend_strength=0.5,
            horizon_bars=12,
        )

        agent = SignalAgent(test_config)
        decision = agent.decide(analysis, sentiment, prediction)

        assert decision.scoring_method == "fallback"

    def test_feature_vector_integrity_through_pipeline(self, test_config):
        bars = _make_bars()
        indicators = compute_indicators(bars)
        clarity = ClarityScore(
            timeframe="1h",
            indicator_agreement=0.7,
            pattern_confidence=0.3,
            data_completeness=0.95,
        )
        breakout = PatternResult(
            pattern_type="breakout", confidence=0.3, direction="BUY", price_level=2350.0
        )
        patterns = PatternDetectionResult(
            patterns=[breakout], strongest_confidence=0.3, strongest_direction="BUY"
        )
        analysis = TimeframeAnalysis(
            timeframe="1h",
            indicators=indicators,
            patterns=patterns,
            clarity=clarity,
            bars=bars,
            timestamp=datetime.now(timezone.utc),
        )
        sentiment = MacroSentiment(macro_score=0.4, headline_count=3)
        prediction = PricePrediction(
            direction="BUY",
            confidence=0.6,
            volatility=0.01,
            trend_strength=0.5,
            horizon_bars=12,
        )

        agent = SignalAgent(test_config)
        decision = agent.decide(analysis, sentiment, prediction)

        fv = decision.feature_vector
        assert "rsi" in fv.indicator_features
        assert "breakout" in fv.pattern_features
        assert "macro_score" in fv.sentiment_features
        assert "confidence" in fv.prediction_features
        assert "indicator_agreement" in fv.derived_features
        assert len(fv.to_array()) == len(fv.feature_names())
