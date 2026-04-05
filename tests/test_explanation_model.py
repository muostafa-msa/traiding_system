from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from core.config import AppConfig
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
    TradeSignal,
    RiskVerdict,
)
from execution.signal_generator import format_trade_signal
from models.explanation_model import ExplanationModel, build_prompt
from tests.conftest import _default_sentiment_fields


def _make_config(**overrides) -> AppConfig:
    defaults = dict(
        market_data_provider="twelvedata",
        market_data_api_key="test",
        initial_capital=10000.0,
        telegram_bot_token="",
        telegram_chat_id="",
        signal_threshold=0.68,
        max_risk_per_trade=0.01,
        max_daily_risk=0.03,
        max_open_positions=2,
        kill_switch_threshold=0.05,
        sl_atr_multiplier=1.5,
        tp_atr_multiplier=3.0,
        log_level="INFO",
        db_path=":memory:",
    )
    defaults.update(_default_sentiment_fields())
    defaults.update(overrides)
    return AppConfig(**defaults)


def _make_indicators() -> IndicatorResult:
    return IndicatorResult(
        rsi=55.0,
        macd_line=0.5,
        macd_signal=0.3,
        macd_hist=0.2,
        ema_20=2310.0,
        ema_50=2300.0,
        ema_200=2280.0,
        bb_upper=2330.0,
        bb_middle=2310.0,
        bb_lower=2290.0,
        atr=15.0,
        support=2290.0,
        resistance=2330.0,
        trend_direction="bullish",
        breakout_probability=0.3,
    )


def _make_decision(direction: str = "BUY", probability: float = 0.85) -> SignalDecision:
    return SignalDecision(
        probability=probability,
        direction=direction,
        explanation="test explanation",
        scoring_method="fallback",
        feature_vector=FeatureVector(),
        timeframe="1h",
        clarity_score=0.75,
    )


class TestBuildPrompt:
    def test_prompt_contains_direction(self):
        prompt = build_prompt(
            direction="BUY",
            probability=0.85,
            trend_direction="bullish",
            rsi=55.0,
            macd_signal="bullish crossover",
            patterns_summary="breakout(75%)",
            sentiment_summary="score=+0.30, headlines=5",
            macro_score=0.3,
            prediction_direction="BUY",
            prediction_confidence=0.65,
        )
        assert "BUY" in prompt
        assert "85%" in prompt
        assert "bullish" in prompt

    def test_prompt_contains_rsi(self):
        prompt = build_prompt(
            direction="SELL",
            probability=0.72,
            trend_direction="bearish",
            rsi=28.0,
            macd_signal="bearish crossover",
            patterns_summary="none detected",
            sentiment_summary="score=-0.20, headlines=3",
            macro_score=-0.2,
            prediction_direction="SELL",
            prediction_confidence=0.60,
        )
        assert "RSI=28" in prompt
        assert "SELL" in prompt
        assert "bearish crossover" in prompt

    def test_prompt_contains_patterns(self):
        prompt = build_prompt(
            direction="BUY",
            probability=0.80,
            trend_direction="bullish",
            rsi=60.0,
            macd_signal="bullish crossover",
            patterns_summary="breakout(75%), triangle(60%)",
            sentiment_summary="score=+0.30, headlines=5",
            macro_score=0.3,
            prediction_direction="BUY",
            prediction_confidence=0.70,
        )
        assert "breakout(75%)" in prompt
        assert "triangle(60%)" in prompt

    def test_prompt_ends_with_explain_instruction(self):
        prompt = build_prompt(
            direction="BUY",
            probability=0.85,
            trend_direction="bullish",
            rsi=55.0,
            macd_signal="bullish crossover",
            patterns_summary="none detected",
            sentiment_summary="score=+0.30, headlines=5",
            macro_score=0.3,
            prediction_direction="BUY",
            prediction_confidence=0.65,
        )
        assert prompt.strip().endswith("Explain why this is a BUY opportunity:")


class TestExplanationModelWithMock:
    def test_explain_returns_generated_text(self):
        config = _make_config()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "The bullish momentum is supported by RSI and breakout pattern."
        }
        mock_response.raise_for_status = MagicMock()

        with patch("models.explanation_model.requests.post", return_value=mock_response) as mock_post:
            model = ExplanationModel(config)
            decision = _make_decision()
            indicators = _make_indicators()
            sentiment = MacroSentiment(macro_score=0.3, headline_count=5)

            result = model.explain(
                decision=decision,
                indicators=indicators,
                sentiment=sentiment,
                prediction_direction="BUY",
                prediction_confidence=0.65,
            )

            assert result is not None
            assert "bullish momentum" in result.lower()
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            assert call_kwargs[1]["json"]["model"] == "gpt-oss:20b"

    def test_explain_returns_none_when_ollama_unavailable(self):
        config = _make_config()

        with patch("models.explanation_model.requests.post") as mock_post:
            mock_post.side_effect = ConnectionError("Connection refused")

            model = ExplanationModel(config)
            decision = _make_decision()
            indicators = _make_indicators()
            sentiment = MacroSentiment()

            result = model.explain(
                decision=decision,
                indicators=indicators,
                sentiment=sentiment,
            )

            assert result is None

    def test_explain_returns_none_on_http_error(self):
        config = _make_config()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("500 Server Error")

        with patch("models.explanation_model.requests.post", return_value=mock_response):
            model = ExplanationModel(config)
            decision = _make_decision()
            indicators = _make_indicators()
            sentiment = MacroSentiment()

            result = model.explain(
                decision=decision,
                indicators=indicators,
                sentiment=sentiment,
            )

            assert result is None

    def test_explain_returns_none_on_empty_response(self):
        config = _make_config()

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": ""}
        mock_response.raise_for_status = MagicMock()

        with patch("models.explanation_model.requests.post", return_value=mock_response):
            model = ExplanationModel(config)
            decision = _make_decision()
            indicators = _make_indicators()
            sentiment = MacroSentiment()

            result = model.explain(
                decision=decision,
                indicators=indicators,
                sentiment=sentiment,
            )

            assert result is None

    def test_uses_config_model_and_url(self):
        config = _make_config(
            ollama_base_url="http://my-server:1234",
            ollama_model="custom-model:latest",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "explanation text"}
        mock_response.raise_for_status = MagicMock()

        with patch("models.explanation_model.requests.post", return_value=mock_response) as mock_post:
            model = ExplanationModel(config)
            decision = _make_decision()
            indicators = _make_indicators()
            sentiment = MacroSentiment()

            model.explain(decision=decision, indicators=indicators, sentiment=sentiment)

            call_args = mock_post.call_args
            assert "http://my-server:1234/api/generate" == call_args[0][0]
            assert call_args[1]["json"]["model"] == "custom-model:latest"


class TestSignalAgentNoTradeSkipsExplanation:
    def test_no_trade_has_empty_explanation(self):
        config = _make_config(signal_threshold=0.68)

        from agents.signal_agent import SignalAgent
        from agents.chart_agent import compute_clarity_score

        agent = SignalAgent(config)

        indicators = _make_indicators()
        bars = [
            OHLCBar(
                timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
                open=2300.0,
                high=2302.0,
                low=2298.0,
                close=2301.0,
                volume=1000.0,
            )
        ] * 250
        patterns = PatternDetectionResult()
        clarity = compute_clarity_score("1h", indicators, patterns, bars)

        analysis = TimeframeAnalysis(
            timeframe="1h",
            indicators=indicators,
            patterns=patterns,
            clarity=clarity,
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

        decision = agent.decide(analysis, sentiment, prediction)
        assert decision.explanation == ""


class TestSignalAgentFallbackOnOllamaFailure:
    def test_template_fallback_when_ollama_fails(self):
        config = _make_config(signal_threshold=0.50)

        from agents.signal_agent import SignalAgent
        from agents.chart_agent import compute_clarity_score

        with patch("models.explanation_model.requests.post") as mock_post:
            mock_post.side_effect = ConnectionError("Ollama not running")

            agent = SignalAgent(config)

            indicators = _make_indicators()
            bars = [
                OHLCBar(
                    timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
                    open=2300.0,
                    high=2302.0,
                    low=2298.0,
                    close=2301.0,
                    volume=1000.0,
                )
            ] * 250
            patterns = PatternDetectionResult(
                patterns=[
                    PatternResult(
                        pattern_type="breakout",
                        confidence=0.8,
                        direction="BUY",
                        price_level=2330.0,
                    )
                ],
                strongest_confidence=0.8,
                strongest_direction="BUY",
            )
            clarity = compute_clarity_score("1h", indicators, patterns, bars)

            analysis = TimeframeAnalysis(
                timeframe="1h",
                indicators=indicators,
                patterns=patterns,
                clarity=clarity,
                bars=bars,
                timestamp=datetime.now(timezone.utc),
            )

            sentiment = MacroSentiment(macro_score=0.5, headline_count=3)
            prediction = PricePrediction(
                direction="BUY",
                confidence=0.7,
                volatility=0.01,
                trend_strength=0.6,
                horizon_bars=12,
            )

            decision = agent.decide(analysis, sentiment, prediction)
            if decision.direction != "NO_TRADE":
                assert decision.explanation != ""
                assert (
                    "BUY" in decision.explanation
                    or "bullish" in decision.explanation.lower()
                )


class TestFormatTradeSignalWithExplanation:
    def test_explanation_shown_in_signal(self):
        signal = TradeSignal(
            asset="XAU/USD",
            direction="BUY",
            entry_price=2350.0,
            stop_loss=2335.0,
            take_profit=2380.0,
            probability=0.85,
            reasoning="Strong bullish momentum with RSI confirming uptrend. Breakout pattern detected at resistance.",
            timeframe="1h",
            timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        )
        risk = RiskVerdict(
            approved=True,
            position_size=0.5,
            rejection_reason=None,
            daily_risk_used=0.01,
            open_positions=1,
        )
        message = format_trade_signal(signal, risk)
        assert "Analysis" in message
        assert "Strong bullish momentum" in message
        assert "Breakout pattern" in message
