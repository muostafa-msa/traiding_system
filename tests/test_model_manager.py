from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from core.config import AppConfig
from core.types import NewsItem
from datetime import datetime, timezone
from models.model_manager import ModelManager
from agents.sentiment_agent import SentimentAgent
from tests.conftest import _default_sentiment_fields


def _default_sentiment_fields_no_device():
    d = _default_sentiment_fields()
    d.pop("model_device")
    return d


def _config_with_device(device: str) -> AppConfig:
    return AppConfig(
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
        **_default_sentiment_fields_no_device(),
        model_device=device,
    )


def _mock_torch(cuda=False, mps=False):
    mock = MagicMock()
    mock.cuda.is_available.return_value = cuda
    mock.backends.mps.is_available.return_value = mps
    return mock


class TestDetectDevice:
    @patch("models.model_manager._get_torch")
    def test_detect_device_returns_cpu_when_no_gpu(self, mock_get):
        mock_get.return_value = _mock_torch(cuda=False, mps=False)
        mgr = ModelManager(_config_with_device("auto"))
        assert mgr.detect_device() == "cpu"

    @patch("models.model_manager._get_torch")
    def test_detect_device_returns_cuda_when_available(self, mock_get):
        mock_get.return_value = _mock_torch(cuda=True, mps=False)
        mgr = ModelManager(_config_with_device("auto"))
        assert mgr.detect_device() == "cuda"

    @patch("models.model_manager._get_torch")
    def test_detect_device_returns_mps_when_no_cuda(self, mock_get):
        mock_get.return_value = _mock_torch(cuda=False, mps=True)
        mgr = ModelManager(_config_with_device("auto"))
        assert mgr.detect_device() == "mps"

    @patch("models.model_manager._get_torch")
    def test_detect_device_cuda_priority_over_mps(self, mock_get):
        mock_get.return_value = _mock_torch(cuda=True, mps=True)
        mgr = ModelManager(_config_with_device("auto"))
        assert mgr.detect_device() == "cuda"

    @patch("models.model_manager._get_torch")
    def test_force_cpu_override(self, mock_get):
        mock_get.return_value = _mock_torch(cuda=True, mps=False)
        mgr = ModelManager(_config_with_device("cpu"))
        assert mgr.detect_device() == "cpu"


class TestLazyLoading:
    @patch("models.model_manager._get_auto_tokenizer")
    @patch("models.model_manager._get_auto_model")
    @patch("models.model_manager._get_torch")
    def test_load_model_lazy_first_call(
        self, mock_get_torch, mock_get_model_cls, mock_get_tok_cls
    ):
        mock_get_torch.return_value = _mock_torch(cuda=False, mps=False)
        mock_model_cls = MagicMock()
        mock_tok_cls = MagicMock()
        mock_get_model_cls.return_value = mock_model_cls
        mock_get_tok_cls.return_value = mock_tok_cls
        mgr = ModelManager(_config_with_device("auto"))
        mgr.load_model("finbert", "models/finbert")
        mock_model_cls.from_pretrained.assert_called_once_with("models/finbert")
        mock_tok_cls.from_pretrained.assert_called_once_with("models/finbert")

    def test_get_model_returns_none_before_load(self):
        mgr = ModelManager(_config_with_device("auto"))
        assert mgr.get_model("finbert") is None


class TestCacheReuse:
    @patch("models.model_manager._get_auto_tokenizer")
    @patch("models.model_manager._get_auto_model")
    @patch("models.model_manager._get_torch")
    def test_second_load_reuses_cache(
        self, mock_get_torch, mock_get_model_cls, mock_get_tok_cls
    ):
        mock_get_torch.return_value = _mock_torch(cuda=False, mps=False)
        mock_get_model_cls.return_value = MagicMock()
        mock_get_tok_cls.return_value = MagicMock()
        mgr = ModelManager(_config_with_device("auto"))
        mgr.load_model("finbert", "models/finbert")
        mgr.load_model("finbert", "models/finbert")
        assert mock_get_model_cls.return_value.from_pretrained.call_count == 1
        assert mock_get_tok_cls.return_value.from_pretrained.call_count == 1

    @patch("models.model_manager._get_auto_tokenizer")
    @patch("models.model_manager._get_auto_model")
    @patch("models.model_manager._get_torch")
    def test_get_model_returns_cached_model(
        self, mock_get_torch, mock_get_model_cls, mock_get_tok_cls
    ):
        mock_get_torch.return_value = _mock_torch(cuda=False, mps=False)
        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        mock_model_cls = MagicMock()
        mock_model_cls.from_pretrained.return_value = mock_model
        mock_tok_cls = MagicMock()
        mock_tok_cls.from_pretrained.return_value = mock_tokenizer
        mock_get_model_cls.return_value = mock_model_cls
        mock_get_tok_cls.return_value = mock_tok_cls
        mgr = ModelManager(_config_with_device("auto"))
        mgr.load_model("finbert", "models/finbert")
        assert mgr.get_model("finbert") is mock_model


class TestLazyLoadIntegration:
    @patch("models.finbert._get_pipeline")
    @patch("models.model_manager._get_torch")
    def test_finbert_loads_lazily_on_first_classify(
        self, mock_get_torch, mock_get_pipeline
    ):
        mock_get_torch.return_value = _mock_torch(cuda=False, mps=False)
        mock_pipeline_fn = MagicMock()
        mock_get_pipeline.return_value = mock_pipeline_fn

        mock_pipe = MagicMock()
        mock_pipeline_fn.return_value = mock_pipe

        mock_pipe.return_value = [
            [
                {"label": "positive", "score": 0.9},
                {"label": "negative", "score": 0.05},
                {"label": "neutral", "score": 0.05},
            ]
        ]

        mgr = ModelManager(_config_with_device("auto"))
        agent = SentimentAgent(_config_with_device("auto"), mgr)
        assert agent._finbert is None

        items = [
            NewsItem(
                headline="Gold surges",
                source="test",
                url="",
                published_at=datetime.now(timezone.utc),
            )
        ]
        agent.classify(items)

        assert agent._finbert is not None
        assert agent._finbert._loaded
        assert mock_pipeline_fn.call_count == 1

    @patch("models.finbert._get_pipeline")
    @patch("models.model_manager._get_torch")
    def test_second_classify_reuses_cached_model(
        self, mock_get_torch, mock_get_pipeline
    ):
        mock_get_torch.return_value = _mock_torch(cuda=False, mps=False)
        mock_pipeline_fn = MagicMock()
        mock_get_pipeline.return_value = mock_pipeline_fn

        mock_pipe = MagicMock()
        mock_pipeline_fn.return_value = mock_pipe

        mock_pipe.return_value = [
            [
                {"label": "positive", "score": 0.9},
                {"label": "negative", "score": 0.05},
                {"label": "neutral", "score": 0.05},
            ]
        ]

        mgr = ModelManager(_config_with_device("auto"))
        agent = SentimentAgent(_config_with_device("auto"), mgr)
        items = [
            NewsItem(
                headline="Gold surges",
                source="test",
                url="",
                published_at=datetime.now(timezone.utc),
            )
        ]

        agent.classify(items)
        assert mock_pipeline_fn.call_count == 1

        mock_pipe.return_value = [
            [
                {"label": "negative", "score": 0.8},
                {"label": "positive", "score": 0.1},
                {"label": "neutral", "score": 0.1},
            ]
        ]
        agent.classify(items)

        assert mock_pipeline_fn.call_count == 1
