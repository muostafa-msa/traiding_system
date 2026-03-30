from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.types import SentimentResult


class TestFinBERTLabelMapping:
    @patch("models.finbert._get_pipeline")
    def test_positive_maps_to_bullish(self, mock_get_pipeline):
        mock_pipe = MagicMock()
        mock_pipe.return_value = [
            [
                {"label": "positive", "score": 0.9},
                {"label": "negative", "score": 0.05},
                {"label": "neutral", "score": 0.05},
            ]
        ]
        mock_get_pipeline.return_value = mock_pipe
        from models.finbert import FinBERTWrapper

        wrapper = FinBERTWrapper.__new__(FinBERTWrapper)
        wrapper._pipeline = mock_pipe
        wrapper._loaded = True
        results = wrapper.classify(["Gold prices surge"])
        assert len(results) == 1
        assert results[0].classification == "Bullish"
        assert results[0].positive_score == 0.9
        assert results[0].negative_score == 0.05
        assert results[0].neutral_score == 0.05

    @patch("models.finbert._get_pipeline")
    def test_negative_maps_to_bearish(self, mock_get_pipeline):
        mock_pipe = MagicMock()
        mock_pipe.return_value = [
            [
                {"label": "negative", "score": 0.85},
                {"label": "positive", "score": 0.10},
                {"label": "neutral", "score": 0.05},
            ]
        ]
        mock_get_pipeline.return_value = mock_pipe
        from models.finbert import FinBERTWrapper

        wrapper = FinBERTWrapper.__new__(FinBERTWrapper)
        wrapper._pipeline = mock_pipe
        wrapper._loaded = True
        results = wrapper.classify(["Fed raises interest rates"])
        assert len(results) == 1
        assert results[0].classification == "Bearish"
        assert results[0].confidence == 0.85

    @patch("models.finbert._get_pipeline")
    def test_neutral_maps_to_neutral(self, mock_get_pipeline):
        mock_pipe = MagicMock()
        mock_pipe.return_value = [
            [
                {"label": "neutral", "score": 0.80},
                {"label": "positive", "score": 0.10},
                {"label": "negative", "score": 0.10},
            ]
        ]
        mock_get_pipeline.return_value = mock_pipe
        from models.finbert import FinBERTWrapper

        wrapper = FinBERTWrapper.__new__(FinBERTWrapper)
        wrapper._pipeline = mock_pipe
        wrapper._loaded = True
        results = wrapper.classify(["Market awaits economic data"])
        assert len(results) == 1
        assert results[0].classification == "Neutral"


class TestFinBERTConfidence:
    @patch("models.finbert._get_pipeline")
    def test_confidence_in_zero_one_range(self, mock_get_pipeline):
        mock_pipe = MagicMock()
        mock_pipe.return_value = [
            [
                {"label": "positive", "score": 0.75},
                {"label": "negative", "score": 0.15},
                {"label": "neutral", "score": 0.10},
            ]
        ]
        mock_get_pipeline.return_value = mock_pipe
        from models.finbert import FinBERTWrapper

        wrapper = FinBERTWrapper.__new__(FinBERTWrapper)
        wrapper._pipeline = mock_pipe
        wrapper._loaded = True
        results = wrapper.classify(["Gold steady"])
        assert 0.0 <= results[0].confidence <= 1.0

    @patch("models.finbert._get_pipeline")
    def test_batch_classify_multiple_headlines(self, mock_get_pipeline):
        mock_pipe = MagicMock()
        mock_pipe.return_value = [
            [
                {"label": "positive", "score": 0.9},
                {"label": "negative", "score": 0.05},
                {"label": "neutral", "score": 0.05},
            ],
            [
                {"label": "negative", "score": 0.8},
                {"label": "positive", "score": 0.10},
                {"label": "neutral", "score": 0.10},
            ],
        ]
        mock_get_pipeline.return_value = mock_pipe
        from models.finbert import FinBERTWrapper

        wrapper = FinBERTWrapper.__new__(FinBERTWrapper)
        wrapper._pipeline = mock_pipe
        wrapper._loaded = True
        results = wrapper.classify(["Gold prices surge", "Fed raises rates"])
        assert len(results) == 2
        assert results[0].classification == "Bullish"
        assert results[1].classification == "Bearish"


class TestFinBERTNotLoaded:
    def test_classify_returns_empty_when_not_loaded(self):
        from models.finbert import FinBERTWrapper

        wrapper = FinBERTWrapper.__new__(FinBERTWrapper)
        wrapper._pipeline = None
        wrapper._loaded = False
        results = wrapper.classify(["Gold prices surge"])
        assert results == []
