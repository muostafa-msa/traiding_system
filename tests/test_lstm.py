from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock

import numpy as np
import pytest
import torch

from core.config import AppConfig
from core.types import OHLCBar, IndicatorResult, PricePrediction
from models.lstm_model import (
    LSTMNet,
    LSTMWrapper,
    INPUT_FEATURES,
    OUTPUT_DIM,
    build_sequences,
    prepare_features_from_bar,
    _neutral_prediction,
    _parse_output,
)
from models.model_manager import ModelManager
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


class TestLSTMNet:
    def test_forward_pass_shape(self):
        model = LSTMNet(
            input_size=INPUT_FEATURES, hidden_size=64, num_layers=1, dropout=0.2
        )
        batch_size = 4
        seq_length = 60
        x = torch.randn(batch_size, seq_length, INPUT_FEATURES)
        output = model(x)
        assert output.shape == (batch_size, OUTPUT_DIM)

    def test_single_sample_forward(self):
        model = LSTMNet()
        x = torch.randn(1, 60, INPUT_FEATURES)
        output = model(x)
        assert output.shape == (1, OUTPUT_DIM)

    def test_default_architecture(self):
        model = LSTMNet()
        assert model.lstm.input_size == INPUT_FEATURES
        assert model.lstm.hidden_size == 64
        assert model.lstm.num_layers == 1
        assert model.fc.out_features == OUTPUT_DIM

    def test_output_is_finite(self):
        model = LSTMNet()
        x = torch.randn(1, 60, INPUT_FEATURES)
        output = model(x)
        assert torch.isfinite(output).all()


class TestPrepareFeatures:
    def test_feature_count(self):
        bar = _make_bar()
        indicators = _make_indicators()
        features = prepare_features_from_bar(bar, indicators)
        assert len(features) == INPUT_FEATURES

    def test_feature_values_finite(self):
        bar = _make_bar()
        indicators = _make_indicators()
        features = prepare_features_from_bar(bar, indicators)
        assert all(np.isfinite(f) for f in features)


class TestBuildSequences:
    def test_sufficient_data(self):
        bars = [_make_bar(i) for i in range(100)]
        indicators = _make_indicators()
        seq = build_sequences(bars, indicators, seq_length=60)
        assert seq is not None
        assert seq.shape == (60, INPUT_FEATURES)

    def test_insufficient_data(self):
        bars = [_make_bar(i) for i in range(30)]
        indicators = _make_indicators()
        seq = build_sequences(bars, indicators, seq_length=60)
        assert seq is None

    def test_exact_sequence_length(self):
        bars = [_make_bar(i) for i in range(60)]
        indicators = _make_indicators()
        seq = build_sequences(bars, indicators, seq_length=60)
        assert seq is not None
        assert seq.shape == (60, INPUT_FEATURES)


class TestParseOutput:
    def test_buy_direction(self):
        raw = np.array([0.8, 0.1, 0.7])
        pred = _parse_output(raw, direction_threshold=0.15)
        assert pred.direction == "BUY"
        assert pred.confidence > 0.0

    def test_sell_direction(self):
        raw = np.array([-0.8, 0.05, 0.3])
        pred = _parse_output(raw, direction_threshold=0.15)
        assert pred.direction == "SELL"
        assert pred.confidence > 0.0

    def test_neutral_direction(self):
        raw = np.array([0.1, 0.02, 0.5])
        pred = _parse_output(raw, direction_threshold=0.15)
        assert pred.direction == "NEUTRAL"

    def test_output_bounds(self):
        raw = np.array([1.5, -0.1, 1.2])
        pred = _parse_output(raw, direction_threshold=0.15)
        assert 0.0 <= pred.confidence <= 1.0
        assert pred.volatility >= 0.0
        assert 0.0 <= pred.trend_strength <= 1.0

    def test_negative_volatility_clamped(self):
        raw = np.array([0.0, -5.0, 0.5])
        pred = _parse_output(raw, direction_threshold=0.15)
        assert pred.volatility == 0.0

    def test_trend_strength_clamped(self):
        raw = np.array([0.0, 0.0, 2.0])
        pred = _parse_output(raw, direction_threshold=0.15)
        assert pred.trend_strength == 1.0


class TestNeutralPrediction:
    def test_neutral_defaults(self):
        pred = _neutral_prediction()
        assert pred.direction == "NEUTRAL"
        assert pred.confidence == 0.0
        assert pred.volatility == 0.0
        assert pred.trend_strength == 0.0
        assert pred.horizon_bars == 12


class TestLSTMWrapper:
    def test_untrained_returns_neutral(self):
        config = _make_config(lstm_model_path="/nonexistent/path")
        mm = ModelManager(config)
        wrapper = LSTMWrapper(config, mm)
        assert not wrapper.is_trained()
        bars = [_make_bar(i) for i in range(100)]
        indicators = _make_indicators()
        pred = wrapper.predict(bars, indicators)
        assert pred.direction == "NEUTRAL"
        assert pred.confidence == 0.0

    def test_insufficient_data_returns_neutral(self):
        config = _make_config(lstm_model_path="/nonexistent/path")
        mm = ModelManager(config)
        wrapper = LSTMWrapper(config, mm)
        wrapper._model = LSTMNet()
        wrapper._model.eval()
        bars = [_make_bar(i) for i in range(10)]
        indicators = _make_indicators()
        pred = wrapper.predict(bars, indicators)
        assert pred.direction == "NEUTRAL"
        assert pred.confidence == 0.0

    def test_prediction_with_model(self):
        config = _make_config(lstm_model_path="/nonexistent/path")
        mm = ModelManager(config)
        wrapper = LSTMWrapper(config, mm)
        wrapper._model = LSTMNet()
        wrapper._model.eval()
        wrapper._device = "cpu"

        bars = [_make_bar(i) for i in range(80)]
        indicators = _make_indicators()
        pred = wrapper.predict(bars, indicators)
        assert pred.direction in ("BUY", "SELL", "NEUTRAL")
        assert 0.0 <= pred.confidence <= 1.0
        assert pred.volatility >= 0.0
        assert 0.0 <= pred.trend_strength <= 1.0
        assert pred.horizon_bars == 12


def _make_training_bars(n: int = 200) -> list[OHLCBar]:
    """Generate bars with a mild uptrend + noise for training tests."""
    bars = []
    base = 2300.0
    for i in range(n):
        drift = i * 0.1
        noise = (i % 7 - 3) * 0.5
        c = base + drift + noise
        bars.append(
            OHLCBar(
                timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
                open=c - 0.5,
                high=c + 2.0,
                low=c - 2.0,
                close=c,
                volume=1000.0 + i * 10,
            )
        )
    return bars


class TestLSTMTraining:
    def test_training_produces_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(lstm_model_path=tmpdir)
            mm = ModelManager(config)
            wrapper = LSTMWrapper(config, mm)
            assert not wrapper.is_trained()

            bars = _make_training_bars(200)
            metrics = wrapper.train(bars, None)

            assert "epochs_trained" in metrics
            assert "best_val_loss" in metrics
            assert "train_samples" in metrics
            assert "val_samples" in metrics
            assert "model_path" in metrics
            assert metrics["epochs_trained"] > 0
            assert metrics["train_samples"] > 0
            assert metrics["val_samples"] > 0

    def test_model_is_trained_after_training(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(lstm_model_path=tmpdir)
            mm = ModelManager(config)
            wrapper = LSTMWrapper(config, mm)
            bars = _make_training_bars(200)
            wrapper.train(bars, None)
            assert wrapper.is_trained()

    def test_training_saves_model_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(lstm_model_path=tmpdir)
            mm = ModelManager(config)
            wrapper = LSTMWrapper(config, mm)
            bars = _make_training_bars(200)
            metrics = wrapper.train(bars, None)
            assert os.path.exists(metrics["model_path"])

    def test_save_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(lstm_model_path=tmpdir)
            mm = ModelManager(config)
            wrapper = LSTMWrapper(config, mm)
            bars = _make_training_bars(200)
            wrapper.train(bars, None)

            indicators = _make_indicators()
            pred1 = wrapper.predict(bars, indicators)

            config2 = _make_config(lstm_model_path=tmpdir)
            mm2 = ModelManager(config2)
            wrapper2 = LSTMWrapper(config2, mm2)
            assert wrapper2.is_trained()

            pred2 = wrapper2.predict(bars, indicators)
            assert pred1.direction == pred2.direction
            assert abs(pred1.confidence - pred2.confidence) < 1e-5

    def test_insufficient_data_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(lstm_model_path=tmpdir)
            mm = ModelManager(config)
            wrapper = LSTMWrapper(config, mm)
            bars = _make_training_bars(50)
            with pytest.raises(ValueError, match="at least"):
                wrapper.train(bars, None)

    def test_trained_model_produces_predictions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(lstm_model_path=tmpdir)
            mm = ModelManager(config)
            wrapper = LSTMWrapper(config, mm)
            bars = _make_training_bars(200)
            wrapper.train(bars, None)

            indicators = _make_indicators()
            pred = wrapper.predict(bars, indicators)
            assert pred.direction in ("BUY", "SELL", "NEUTRAL")
            assert 0.0 <= pred.confidence <= 1.0
            assert pred.volatility >= 0.0
            assert 0.0 <= pred.trend_strength <= 1.0
