from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

from core.config import AppConfig
from core.types import FeatureVector
from models.xgboost_model import XGBoostWrapper
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


def _make_feature_vector(label: int = 0) -> FeatureVector:
    rng = np.random.default_rng(hash(str(label)) % (2**31))
    return FeatureVector(
        indicator_features={
            "rsi": rng.uniform(0.2, 0.8),
            "macd_line": rng.uniform(-1, 1),
            "macd_signal": rng.uniform(-1, 1),
            "macd_hist": rng.uniform(-0.5, 0.5),
            "ema_ratio_20": rng.uniform(0.98, 1.02),
            "ema_ratio_50": rng.uniform(0.96, 1.04),
            "ema_ratio_200": rng.uniform(0.93, 1.07),
            "bb_position": rng.uniform(0.1, 0.9),
            "atr_normalized": rng.uniform(0.001, 0.02),
        },
        pattern_features={
            "breakout": rng.uniform(0, 0.8),
            "triangle": rng.uniform(0, 0.5),
            "double_top": 0.0,
            "double_bottom": 0.0,
            "head_shoulders": 0.0,
            "range": rng.uniform(0, 0.3),
        },
        sentiment_features={
            "macro_score": rng.uniform(-0.5, 0.5),
            "headline_count": float(rng.integers(0, 10)),
            "is_blackout": 0.0,
        },
        prediction_features={
            "direction_encoded": float(label * 2 - 1),
            "confidence": rng.uniform(0.1, 0.9),
            "volatility": rng.uniform(0.001, 0.05),
            "trend_strength": rng.uniform(0.1, 0.9),
        },
        derived_features={
            "indicator_agreement": rng.uniform(0.3, 0.9),
            "trend_encoded": float(label * 2 - 1),
            "price_vs_support": rng.uniform(0.99, 1.05),
            "price_vs_resistance": rng.uniform(0.95, 1.01),
        },
    )


def _make_synthetic_data(n: int = 100):
    rng = np.random.default_rng(42)
    feature_vectors = []
    labels = []
    for i in range(n):
        label = int(rng.integers(0, 2))
        fv = _make_feature_vector(label)
        feature_vectors.append(fv)
        labels.append(label)
    return feature_vectors, labels


class TestFeatureEngineering:
    def test_to_array_length(self):
        fv = _make_feature_vector()
        arr = fv.to_array()
        assert len(arr) == len(fv.feature_names())

    def test_feature_names_ordering(self):
        fv = _make_feature_vector()
        names = fv.feature_names()
        assert names == sorted(fv.indicator_features.keys()) + sorted(
            fv.pattern_features.keys()
        ) + sorted(fv.sentiment_features.keys()) + sorted(
            fv.prediction_features.keys()
        ) + sorted(fv.derived_features.keys())

    def test_to_array_values_finite(self):
        fv = _make_feature_vector()
        arr = fv.to_array()
        assert all(np.isfinite(v) for v in arr)

    def test_multiple_feature_vectors_consistent_features(self):
        fvs = [_make_feature_vector(i) for i in range(5)]
        names = [fv.feature_names() for fv in fvs]
        for n in names[1:]:
            assert n == names[0]


class TestXGBoostTraining:
    def test_training_produces_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(xgboost_model_path=os.path.join(tmpdir, "xgb"))
            wrapper = XGBoostWrapper(config)
            assert not wrapper.is_trained()

            fvs, labels = _make_synthetic_data(100)
            metrics = wrapper.train(fvs, labels)

            assert "train_samples" in metrics
            assert "val_samples" in metrics
            assert "val_logloss" in metrics
            assert "val_accuracy" in metrics
            assert "model_path" in metrics
            assert metrics["train_samples"] == 80
            assert metrics["val_samples"] == 20

    def test_model_is_trained_after_training(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(xgboost_model_path=os.path.join(tmpdir, "xgb"))
            wrapper = XGBoostWrapper(config)
            fvs, labels = _make_synthetic_data(100)
            wrapper.train(fvs, labels)
            assert wrapper.is_trained()

    def test_training_saves_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = os.path.join(tmpdir, "xgb")
            config = _make_config(xgboost_model_path=model_dir)
            wrapper = XGBoostWrapper(config)
            fvs, labels = _make_synthetic_data(100)
            wrapper.train(fvs, labels)

            assert os.path.exists(os.path.join(model_dir, "model.json"))
            assert os.path.exists(os.path.join(model_dir, "classifier.pkl"))

    def test_minimum_samples_required(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(xgboost_model_path=os.path.join(tmpdir, "xgb"))
            wrapper = XGBoostWrapper(config)
            fvs, labels = _make_synthetic_data(10)
            with pytest.raises(ValueError, match="at least 20"):
                wrapper.train(fvs, labels)

    def test_mismatched_lengths_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(xgboost_model_path=os.path.join(tmpdir, "xgb"))
            wrapper = XGBoostWrapper(config)
            fvs, _ = _make_synthetic_data(50)
            with pytest.raises(ValueError, match="same length"):
                wrapper.train(fvs, [1, 0])


class TestXGBoostSaveLoadRoundTrip:
    def test_save_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = os.path.join(tmpdir, "xgb")
            config = _make_config(xgboost_model_path=model_dir)
            wrapper = XGBoostWrapper(config)
            fvs, labels = _make_synthetic_data(100)
            wrapper.train(fvs, labels)

            test_fv = fvs[0]
            pred1 = wrapper.predict(test_fv)

            config2 = _make_config(xgboost_model_path=model_dir)
            wrapper2 = XGBoostWrapper(config2)
            assert wrapper2.is_trained()

            pred2 = wrapper2.predict(test_fv)
            assert abs(pred1 - pred2) < 1e-6


class TestXGBoostInference:
    def test_prediction_in_valid_range(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(xgboost_model_path=os.path.join(tmpdir, "xgb"))
            wrapper = XGBoostWrapper(config)
            fvs, labels = _make_synthetic_data(100)
            wrapper.train(fvs, labels)

            for fv in fvs[:10]:
                prob = wrapper.predict(fv)
                assert 0.0 <= prob <= 1.0

    def test_untrained_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(xgboost_model_path=os.path.join(tmpdir, "xgb"))
            wrapper = XGBoostWrapper(config)
            fv = _make_feature_vector()
            assert wrapper.predict(fv) == 0.0

    def test_calibrated_probabilities_are_calibrated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(xgboost_model_path=os.path.join(tmpdir, "xgb"))
            wrapper = XGBoostWrapper(config)
            fvs, labels = _make_synthetic_data(200)
            wrapper.train(fvs, labels)

            probs = [wrapper.predict(fv) for fv in fvs]
            assert all(0.0 <= p <= 1.0 for p in probs)
            assert len(set(round(p, 4) for p in probs)) > 1
