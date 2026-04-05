from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from agents.prediction_agent import PredictionAgent
from core.config import AppConfig
from core.types import OHLCBar, IndicatorResult, PricePrediction
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


def _make_bar(i: int = 0) -> OHLCBar:
    base = 2300.0 + i * 0.5
    return OHLCBar(
        timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        open=base,
        high=base + 2.0,
        low=base - 2.0,
        close=base + 1.0,
        volume=1000.0,
    )


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


class TestPredictionAgentWithMock:
    def test_returns_prediction_from_lstm(self):
        config = _make_config(lstm_model_path="/nonexistent/path")
        mock_prediction = PricePrediction(
            direction="BUY",
            confidence=0.72,
            volatility=0.015,
            trend_strength=0.8,
            horizon_bars=12,
        )

        with patch("agents.prediction_agent.LSTMWrapper") as MockLSTM:
            mock_lstm = MockLSTM.return_value
            mock_lstm.predict.return_value = mock_prediction

            agent = PredictionAgent(config, MagicMock())
            bars = [_make_bar(i) for i in range(80)]
            indicators = _make_indicators()
            result = agent.predict(bars, indicators)

            assert result.direction == "BUY"
            assert result.confidence == 0.72
            assert result.volatility == 0.015
            assert result.trend_strength == 0.8
            mock_lstm.predict.assert_called_once_with(bars, indicators)

    def test_fallback_on_model_failure(self):
        config = _make_config(lstm_model_path="/nonexistent/path")

        with patch("agents.prediction_agent.LSTMWrapper") as MockLSTM:
            mock_lstm = MockLSTM.return_value
            mock_lstm.predict.side_effect = RuntimeError("Model crashed")

            agent = PredictionAgent(config, MagicMock())
            bars = [_make_bar(i) for i in range(80)]
            indicators = _make_indicators()
            result = agent.predict(bars, indicators)

            assert result.direction == "NEUTRAL"
            assert result.confidence == 0.0
            assert result.volatility == 0.0
            assert result.trend_strength == 0.0
            assert result.horizon_bars == 12

    def test_fallback_on_generic_exception(self):
        config = _make_config(lstm_model_path="/nonexistent/path")

        with patch("agents.prediction_agent.LSTMWrapper") as MockLSTM:
            mock_lstm = MockLSTM.return_value
            mock_lstm.predict.side_effect = ValueError("Bad data")

            agent = PredictionAgent(config, MagicMock())
            bars = [_make_bar(i) for i in range(80)]
            indicators = _make_indicators()
            result = agent.predict(bars, indicators)

            assert result.direction == "NEUTRAL"
            assert result.confidence == 0.0

    def test_neutral_prediction_when_untrained(self):
        config = _make_config(lstm_model_path="/nonexistent/path")

        with patch("agents.prediction_agent.LSTMWrapper") as MockLSTM:
            mock_lstm = MockLSTM.return_value
            mock_lstm.predict.return_value = PricePrediction(
                direction="NEUTRAL",
                confidence=0.0,
                volatility=0.0,
                trend_strength=0.0,
                horizon_bars=12,
            )

            agent = PredictionAgent(config, MagicMock())
            bars = [_make_bar(i) for i in range(80)]
            indicators = _make_indicators()
            result = agent.predict(bars, indicators)

            assert result.direction == "NEUTRAL"
            assert result.confidence == 0.0

    def test_sell_prediction_passed_through(self):
        config = _make_config(lstm_model_path="/nonexistent/path")
        mock_prediction = PricePrediction(
            direction="SELL",
            confidence=0.65,
            volatility=0.02,
            trend_strength=0.4,
            horizon_bars=12,
        )

        with patch("agents.prediction_agent.LSTMWrapper") as MockLSTM:
            mock_lstm = MockLSTM.return_value
            mock_lstm.predict.return_value = mock_prediction

            agent = PredictionAgent(config, MagicMock())
            bars = [_make_bar(i) for i in range(80)]
            indicators = _make_indicators()
            result = agent.predict(bars, indicators)

            assert result.direction == "SELL"
            assert result.confidence == 0.65
