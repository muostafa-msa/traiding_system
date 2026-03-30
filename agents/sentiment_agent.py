from __future__ import annotations

from core.config import AppConfig
from core.logger import get_logger
from core.types import NewsItem, SentimentResult
from models.finbert import FinBERTWrapper
from models.model_manager import ModelManager

logger = get_logger(__name__)


class SentimentAgent:
    def __init__(self, config: AppConfig, model_manager: ModelManager):
        self._config = config
        self._model_manager = model_manager
        self._finbert: FinBERTWrapper | None = None

    def _ensure_model(self) -> FinBERTWrapper | None:
        if self._finbert is not None:
            return self._finbert
        try:
            device = self._model_manager.detect_device()
            self._finbert = FinBERTWrapper(
                model_path=self._config.finbert_model_path,
                device=device,
            )
            self._finbert.load()
            return self._finbert
        except Exception as e:
            logger.warning("Failed to initialize FinBERT: %s", e)
            return None

    def classify(self, news_items: list[NewsItem]) -> list[SentimentResult]:
        if not news_items:
            return []
        finbert = self._ensure_model()
        if finbert is None or not finbert._loaded:
            logger.warning("SentimentAgent: model unavailable, returning empty results")
            return []
        headlines = [item.headline for item in news_items]
        return finbert.classify(headlines)
