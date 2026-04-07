from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agents.signal_agent import (
    SignalAgent,
    assemble_features,
    compute_opportunity_score,
    template_explain,
    weighted_formula,
    _determine_fallback_direction,
)
from core.types import (
    ClarityScore,
    FeatureVector,
    IndicatorResult,
    MacroSentiment,
    PatternDetectionResult,
    PatternResult,
    PricePrediction,
    SignalDecision,
    TimeframeAnalysis,
)


@pytest.fixture
def bullish_indicators() -> IndicatorResult:
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


@pytest.fixture
def bearish_indicators() -> IndicatorResult:
    return IndicatorResult(
        rsi=35.0,
        macd_line=-2.0,
        macd_signal=-1.5,
        macd_hist=-0.5,
        ema_20=2340.0,
        ema_50=2350.0,
        ema_200=2360.0,
        bb_upper=2360.0,
        bb_middle=2350.0,
        bb_lower=2340.0,
        atr=15.0,
        support=2340.0,
        resistance=2360.0,
        trend_direction="bearish",
        breakout_probability=0.3,
    )


@pytest.fixture
def bullish_analysis(bullish_indicators: IndicatorResult) -> TimeframeAnalysis:
    clarity = ClarityScore(
        timeframe="1h",
        indicator_agreement=0.85,
        pattern_confidence=0.7,
        data_completeness=1.0,
    )
    breakout = PatternResult(
        pattern_type="breakout",
        confidence=0.7,
        direction="BUY",
        price_level=2360.0,
    )
    patterns = PatternDetectionResult(
        patterns=[breakout],
        strongest_confidence=0.7,
        strongest_direction="BUY",
    )
    from core.types import OHLCBar

    bars = [
        OHLCBar(
            timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            open=2345.0,
            high=2355.0,
            low=2340.0,
            close=2350.0,
            volume=1000.0,
        )
    ]
    return TimeframeAnalysis(
        timeframe="1h",
        indicators=bullish_indicators,
        patterns=patterns,
        clarity=clarity,
        bars=bars,
        timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
    )


class TestWeightedFormula:
    def test_all_max_inputs_gives_high_probability(self, test_config):
        prob = weighted_formula(1.0, 1.0, 1.0, 1.0, test_config)
        assert prob == pytest.approx(1.0, abs=0.01)

    def test_all_zero_inputs_gives_zero_probability(self, test_config):
        prob = weighted_formula(0.0, 0.0, 0.0, 0.0, test_config)
        assert prob == pytest.approx(0.0, abs=0.01)

    def test_partial_inputs_gives_moderate_probability(self, test_config):
        prob = weighted_formula(0.8, 0.5, 0.3, 0.6, test_config)
        expected = (
            test_config.fallback_weight_indicators * 0.8
            + test_config.fallback_weight_patterns * 0.5
            + test_config.fallback_weight_sentiment * 0.3
            + test_config.fallback_weight_prediction * 0.6
        )
        assert prob == pytest.approx(expected, abs=0.001)

    def test_probability_clamped_to_one(self, test_config):
        prob = weighted_formula(1.5, 1.5, 1.5, 1.5, test_config)
        assert prob == 1.0

    def test_negative_macro_score_uses_absolute(self, test_config):
        prob_pos = weighted_formula(0.5, 0.5, 0.5, 0.5, test_config)
        prob_neg = weighted_formula(0.5, 0.5, -0.5, 0.5, test_config)
        assert prob_pos == pytest.approx(prob_neg, abs=0.001)


class TestFallbackDirection:
    def test_all_bullish_gives_buy(self):
        direction = _determine_fallback_direction("bullish", "BUY", 0.5)
        assert direction == "BUY"

    def test_all_bearish_gives_sell(self):
        direction = _determine_fallback_direction("bearish", "SELL", -0.5)
        assert direction == "SELL"

    def test_tie_produces_no_trade(self):
        direction = _determine_fallback_direction("bullish", "SELL", 0.0)
        assert direction == "NO_TRADE"

    def test_no_signals_produces_no_trade(self):
        direction = _determine_fallback_direction("neutral", "NEUTRAL", 0.0)
        assert direction == "NO_TRADE"

    def test_two_buy_one_sell_gives_buy(self):
        direction = _determine_fallback_direction("bullish", "BUY", -0.3)
        assert direction == "BUY"


class TestTemplateExplain:
    def test_produces_non_empty_explanation(self):
        result = template_explain(
            direction="BUY",
            probability=0.85,
            trend_direction="bullish",
            rsi=65.0,
            macd_signal="bullish crossover",
            patterns_summary="breakout(70%)",
            sentiment_summary="score=+0.30",
            prediction_summary="BUY (65% confidence)",
        )
        assert "BUY" in result
        assert "85%" in result
        assert "bullish" in result
        assert "breakout" in result

    def test_no_patterns_no_sentiment(self):
        result = template_explain(
            direction="SELL",
            probability=0.70,
            trend_direction="bearish",
            rsi=35.0,
            macd_signal="bearish crossover",
            patterns_summary="",
            sentiment_summary="",
            prediction_summary="",
        )
        assert "SELL" in result
        assert "70%" in result


class TestAssembleFeatures:
    def test_assembles_all_feature_groups(self, bullish_analysis):
        sentiment = MacroSentiment(macro_score=0.3, headline_count=5)
        prediction = PricePrediction(
            direction="BUY",
            confidence=0.6,
            volatility=0.02,
            trend_strength=0.7,
            horizon_bars=12,
        )
        fv = assemble_features(bullish_analysis, sentiment, prediction)

        assert len(fv.indicator_features) == 9
        assert len(fv.pattern_features) == 6
        assert len(fv.sentiment_features) == 3
        assert len(fv.prediction_features) == 4
        assert len(fv.derived_features) == 4

    def test_neutral_defaults_for_missing_prediction(self, bullish_analysis):
        sentiment = MacroSentiment(macro_score=0.0, headline_count=0)
        prediction = PricePrediction(
            direction="NEUTRAL",
            confidence=0.0,
            volatility=0.0,
            trend_strength=0.0,
            horizon_bars=12,
        )
        fv = assemble_features(bullish_analysis, sentiment, prediction)
        assert fv.prediction_features["confidence"] == 0.0
        assert fv.prediction_features["direction_encoded"] == 0.0

    def test_to_array_returns_all_features(self, bullish_analysis):
        sentiment = MacroSentiment(macro_score=0.3)
        prediction = PricePrediction(
            direction="BUY",
            confidence=0.6,
            volatility=0.02,
            trend_strength=0.7,
            horizon_bars=12,
        )
        fv = assemble_features(bullish_analysis, sentiment, prediction)
        arr = fv.to_array()
        assert len(arr) == len(fv.feature_names())
        assert all(isinstance(v, float) for v in arr)


class TestSignalAgentDecide:
    def test_high_probability_bullish_produces_buy(self, test_config, bullish_analysis):
        agent = SignalAgent(test_config)
        sentiment = MacroSentiment(macro_score=0.5, headline_count=5)
        prediction = PricePrediction(
            direction="BUY",
            confidence=0.8,
            volatility=0.02,
            trend_strength=0.8,
            horizon_bars=12,
        )
        decision = agent.decide(bullish_analysis, sentiment, prediction)
        assert decision.direction == "BUY"
        assert decision.probability >= test_config.signal_threshold
        assert decision.explanation != ""
        assert decision.scoring_method == "fallback"

    def test_low_probability_produces_no_trade(self, test_config, bullish_analysis):
        agent = SignalAgent(test_config)
        sentiment = MacroSentiment(macro_score=0.0, headline_count=0)
        prediction = PricePrediction(
            direction="NEUTRAL",
            confidence=0.0,
            volatility=0.0,
            trend_strength=0.0,
            horizon_bars=12,
        )
        low_clarity = ClarityScore(
            timeframe="1h",
            indicator_agreement=0.1,
            pattern_confidence=0.0,
            data_completeness=0.5,
        )
        low_analysis = TimeframeAnalysis(
            timeframe="1h",
            indicators=bullish_analysis.indicators,
            patterns=PatternDetectionResult(),
            clarity=low_clarity,
            bars=bullish_analysis.bars,
            timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        )
        decision = agent.decide(low_analysis, sentiment, prediction)
        assert decision.direction == "NO_TRADE"
        assert decision.explanation == ""

    def test_threshold_enforcement(self, test_config, bullish_analysis):
        agent = SignalAgent(test_config)
        sentiment = MacroSentiment(macro_score=0.0, headline_count=0)
        prediction = PricePrediction(
            direction="NEUTRAL",
            confidence=0.0,
            volatility=0.0,
            trend_strength=0.0,
            horizon_bars=12,
        )
        decision = agent.decide(bullish_analysis, sentiment, prediction)
        if decision.probability < test_config.signal_threshold:
            assert decision.direction == "NO_TRADE"
            assert decision.explanation == ""

    def test_scoring_method_is_fallback_without_xgboost(
        self, test_config, bullish_analysis
    ):
        agent = SignalAgent(test_config)
        sentiment = MacroSentiment(macro_score=0.3)
        prediction = PricePrediction(
            direction="BUY",
            confidence=0.5,
            volatility=0.01,
            trend_strength=0.5,
            horizon_bars=12,
        )
        decision = agent.decide(bullish_analysis, sentiment, prediction)
        assert decision.scoring_method == "fallback"

    def test_partial_features_with_neutral_defaults(
        self, test_config, bullish_indicators
    ):
        agent = SignalAgent(test_config)
        clarity = ClarityScore(
            timeframe="1h",
            indicator_agreement=0.5,
            pattern_confidence=0.0,
            data_completeness=1.0,
        )
        from core.types import OHLCBar

        bars = [
            OHLCBar(
                timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
                open=2345.0,
                high=2355.0,
                low=2340.0,
                close=2350.0,
                volume=1000.0,
            )
        ]
        analysis = TimeframeAnalysis(
            timeframe="1h",
            indicators=bullish_indicators,
            patterns=PatternDetectionResult(),
            clarity=clarity,
            bars=bars,
            timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        )
        sentiment = MacroSentiment()
        prediction = PricePrediction(
            direction="NEUTRAL",
            confidence=0.0,
            volatility=0.0,
            trend_strength=0.0,
            horizon_bars=12,
        )
        decision = agent.decide(analysis, sentiment, prediction)
        assert decision is not None
        assert 0.0 <= decision.probability <= 1.0


class TestBestSignalWins:
    def test_higher_probability_signal_passes(self, test_config, bullish_analysis):
        agent = SignalAgent(test_config)
        agent._recent_decisions = []
        sentiment = MacroSentiment(macro_score=0.5, headline_count=5)
        prediction = PricePrediction(
            direction="BUY",
            confidence=0.8,
            volatility=0.02,
            trend_strength=0.8,
            horizon_bars=12,
        )
        decision = agent.decide(bullish_analysis, sentiment, prediction)
        if decision.direction != "NO_TRADE":
            assert decision.probability >= 0.68


class TestXGBoostWrapper:
    def test_is_trained_false_when_no_model(self, test_config):
        from models.xgboost_model import XGBoostWrapper

        wrapper = XGBoostWrapper(test_config)
        assert wrapper.is_trained() is False

    def test_predict_returns_zero_when_not_trained(self, test_config):
        from models.xgboost_model import XGBoostWrapper

        wrapper = XGBoostWrapper(test_config)
        fv = FeatureVector(indicator_features={"rsi": 0.55})
        assert wrapper.predict(fv) == 0.0


def _make_bullish_analysis(
    indicator_agreement: float = 0.85,
    pattern_confidence: float = 0.7,
    trend_direction: str = "bullish",
) -> TimeframeAnalysis:
    indicators = IndicatorResult(
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
        trend_direction=trend_direction,
        breakout_probability=0.4,
    )
    clarity = ClarityScore(
        timeframe="1h",
        indicator_agreement=indicator_agreement,
        pattern_confidence=pattern_confidence,
        data_completeness=1.0,
    )
    breakout = PatternResult(
        pattern_type="breakout",
        confidence=pattern_confidence,
        direction="BUY" if trend_direction == "bullish" else "SELL",
        price_level=2360.0,
    )
    patterns = PatternDetectionResult(
        patterns=[breakout],
        strongest_confidence=pattern_confidence,
        strongest_direction="BUY" if trend_direction == "bullish" else "SELL",
    )
    from core.types import OHLCBar

    bars = [
        OHLCBar(
            timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            open=2345.0,
            high=2355.0,
            low=2340.0,
            close=2350.0,
            volume=1000.0,
        )
    ]
    return TimeframeAnalysis(
        timeframe="1h",
        indicators=indicators,
        patterns=patterns,
        clarity=clarity,
        bars=bars,
        timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
    )


def _make_bearish_analysis(
    indicator_agreement: float = 0.85,
    pattern_confidence: float = 0.7,
) -> TimeframeAnalysis:
    indicators = IndicatorResult(
        rsi=35.0,
        macd_line=-2.0,
        macd_signal=-1.5,
        macd_hist=-0.5,
        ema_20=2340.0,
        ema_50=2350.0,
        ema_200=2360.0,
        bb_upper=2360.0,
        bb_middle=2350.0,
        bb_lower=2340.0,
        atr=15.0,
        support=2340.0,
        resistance=2360.0,
        trend_direction="bearish",
        breakout_probability=0.3,
    )
    clarity = ClarityScore(
        timeframe="1h",
        indicator_agreement=indicator_agreement,
        pattern_confidence=pattern_confidence,
        data_completeness=1.0,
    )
    dt = PatternResult(
        pattern_type="double_top",
        confidence=pattern_confidence,
        direction="SELL",
        price_level=2350.0,
    )
    patterns = PatternDetectionResult(
        patterns=[dt],
        strongest_confidence=pattern_confidence,
        strongest_direction="SELL",
    )
    from core.types import OHLCBar

    bars = [
        OHLCBar(
            timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            open=2345.0,
            high=2355.0,
            low=2340.0,
            close=2350.0,
            volume=1000.0,
        )
    ]
    return TimeframeAnalysis(
        timeframe="1h",
        indicators=indicators,
        patterns=patterns,
        clarity=clarity,
        bars=bars,
        timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
    )


class TestPredictionAgreement:
    def test_buy_signal_buy_prediction_passes(self, test_config):
        agent = SignalAgent(test_config)
        agent._xgboost._model = None
        agent._xgboost._classifier = None
        analysis = _make_bullish_analysis()
        sentiment = MacroSentiment(macro_score=0.5, headline_count=5)
        prediction = PricePrediction(
            direction="BUY",
            confidence=0.8,
            volatility=0.02,
            trend_strength=0.8,
            horizon_bars=12,
        )
        decision = agent.decide(analysis, sentiment, prediction)
        assert decision.direction == "BUY"

    def test_sell_signal_sell_prediction_passes(self, test_config):
        agent = SignalAgent(test_config)
        agent._xgboost._model = None
        agent._xgboost._classifier = None
        analysis = _make_bearish_analysis()
        sentiment = MacroSentiment(macro_score=-0.5, headline_count=5)
        prediction = PricePrediction(
            direction="SELL",
            confidence=0.8,
            volatility=0.02,
            trend_strength=0.8,
            horizon_bars=12,
        )
        decision = agent.decide(analysis, sentiment, prediction)
        assert decision.direction == "SELL"

    def test_buy_signal_sell_prediction_rejected(self, test_config):
        agent = SignalAgent(test_config)
        analysis = _make_bullish_analysis()
        sentiment = MacroSentiment(macro_score=0.5, headline_count=5)
        prediction = PricePrediction(
            direction="SELL",
            confidence=0.8,
            volatility=0.02,
            trend_strength=0.3,
            horizon_bars=12,
        )
        decision = agent.decide(analysis, sentiment, prediction)
        assert decision.direction == "NO_TRADE"

    def test_sell_signal_neutral_prediction_rejected(self, test_config):
        agent = SignalAgent(test_config)
        analysis = _make_bearish_analysis()
        sentiment = MacroSentiment(macro_score=-0.5, headline_count=5)
        prediction = PricePrediction(
            direction="NEUTRAL",
            confidence=0.5,
            volatility=0.02,
            trend_strength=0.3,
            horizon_bars=12,
        )
        decision = agent.decide(analysis, sentiment, prediction)
        assert decision.direction == "NO_TRADE"

    def test_prediction_agreement_disabled_passes(self, test_config):
        config = test_config
        from dataclasses import replace

        config = replace(config, prediction_agreement_enabled=False)
        agent = SignalAgent(config)
        analysis = _make_bullish_analysis()
        sentiment = MacroSentiment(macro_score=0.5, headline_count=5)
        prediction = PricePrediction(
            direction="SELL",
            confidence=0.8,
            volatility=0.02,
            trend_strength=0.3,
            horizon_bars=12,
        )
        decision = agent.decide(analysis, sentiment, prediction)
        assert (
            decision.direction != "NO_TRADE"
            or decision.probability < config.signal_threshold
        )

    def test_lstm_unavailable_bypasses_gate(self, test_config):
        agent = SignalAgent(test_config)
        analysis = _make_bullish_analysis()
        sentiment = MacroSentiment(macro_score=0.5, headline_count=5)
        prediction = PricePrediction(
            direction="NEUTRAL",
            confidence=0.0,
            volatility=0.0,
            trend_strength=0.0,
            horizon_bars=12,
        )
        decision = agent.decide(analysis, sentiment, prediction)
        assert (
            decision.direction != "NO_TRADE"
            or decision.probability < test_config.signal_threshold
        )


class TestAllGatesDisabled:
    def test_decide_matches_baseline_when_gates_disabled(self, test_config):
        from dataclasses import replace

        config = replace(
            test_config,
            prediction_agreement_enabled=False,
            opportunity_score_enabled=False,
            mtf_confirmation_enabled=False,
        )
        agent_enabled = SignalAgent(config)
        from dataclasses import replace as _replace

        config_all_off = _replace(
            test_config,
            prediction_agreement_enabled=False,
            opportunity_score_enabled=False,
            mtf_confirmation_enabled=False,
        )
        agent_disabled = SignalAgent(config_all_off)

        analysis = _make_bullish_analysis()
        sentiment = MacroSentiment(macro_score=0.5, headline_count=5)
        prediction = PricePrediction(
            direction="BUY",
            confidence=0.8,
            volatility=0.02,
            trend_strength=0.8,
            horizon_bars=12,
        )
        d1 = agent_enabled.decide(analysis, sentiment, prediction)
        d2 = agent_disabled.decide(analysis, sentiment, prediction)
        assert d1.direction == d2.direction
        assert d1.probability == pytest.approx(d2.probability, abs=0.001)


class TestOpportunityScore:
    def test_all_strong_components_passes(self, test_config):
        agent = SignalAgent(test_config)
        agent._xgboost._model = None
        agent._xgboost._classifier = None
        analysis = _make_bullish_analysis(
            indicator_agreement=0.9, pattern_confidence=0.85
        )
        sentiment = MacroSentiment(macro_score=0.8, headline_count=5)
        prediction = PricePrediction(
            direction="BUY",
            confidence=0.85,
            volatility=0.02,
            trend_strength=0.9,
            horizon_bars=12,
        )
        decision = agent.decide(
            analysis, sentiment, prediction, mtf_agreement_fraction=0.75
        )
        assert decision.direction == "BUY"

    def test_mixed_weak_components_rejected(self, test_config):
        from dataclasses import replace

        config = replace(
            test_config,
            prediction_agreement_enabled=False,
        )
        agent = SignalAgent(config)
        agent._xgboost._model = None
        agent._xgboost._classifier = None
        analysis = _make_bullish_analysis(
            indicator_agreement=0.2, pattern_confidence=0.1
        )
        sentiment = MacroSentiment(macro_score=0.0, headline_count=0)
        prediction = PricePrediction(
            direction="BUY",
            confidence=0.1,
            volatility=0.001,
            trend_strength=0.1,
            horizon_bars=12,
        )
        decision = agent.decide(
            analysis, sentiment, prediction, mtf_agreement_fraction=0.0
        )
        assert decision.direction == "NO_TRADE"

    def test_opportunity_score_disabled_passes(self, test_config):
        from dataclasses import replace

        config = replace(
            test_config,
            prediction_agreement_enabled=False,
            opportunity_score_enabled=False,
        )
        agent = SignalAgent(config)
        agent._xgboost._model = None
        agent._xgboost._classifier = None
        analysis = _make_bullish_analysis(
            indicator_agreement=0.2, pattern_confidence=0.1
        )
        sentiment = MacroSentiment(macro_score=0.0, headline_count=0)
        prediction = PricePrediction(
            direction="BUY",
            confidence=0.1,
            volatility=0.001,
            trend_strength=0.1,
            horizon_bars=12,
        )
        decision = agent.decide(
            analysis, sentiment, prediction, mtf_agreement_fraction=0.0
        )
        assert (
            decision.direction != "NO_TRADE"
            or decision.probability < config.signal_threshold
        )

    def test_compute_opportunity_score_defaults(self):
        analysis = _make_bullish_analysis(
            indicator_agreement=0.5, pattern_confidence=0.3
        )
        sentiment = MacroSentiment(macro_score=0.0, headline_count=0)
        prediction = PricePrediction(
            direction="BUY",
            confidence=0.5,
            volatility=0.01,
            trend_strength=0.5,
            horizon_bars=12,
        )
        score = compute_opportunity_score(
            analysis, prediction, sentiment, "BUY", mtf_agreement_fraction=0.0
        )
        assert score.indicator_agreement == 0.5
        assert score.pattern_confidence == 0.3
        assert score.prediction_confidence == 0.5
        assert score.trend_strength == 0.5
        assert score.mtf_agreement == 0.0
        assert 0.0 <= score.composite <= 1.0
