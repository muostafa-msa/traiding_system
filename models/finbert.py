from __future__ import annotations

import importlib

from core.logger import get_logger
from core.types import SentimentResult

logger = get_logger(__name__)

LABEL_MAP = {
    "positive": "Bullish",
    "negative": "Bearish",
    "neutral": "Neutral",
}


def _get_pipeline():
    mod = importlib.import_module("transformers")
    return mod.pipeline


class FinBERTWrapper:
    def __init__(self, model_path: str, device: str = "cpu"):
        self._model_path = model_path
        self._device = device
        self._pipeline = None
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        try:
            pipeline_fn = _get_pipeline()
            device_int = -1
            if self._device == "cuda":
                device_int = 0
            elif self._device == "mps":
                device_int = "mps"

            self._pipeline = pipeline_fn(
                "text-classification",
                model=self._model_path,
                tokenizer=self._model_path,
                device=device_int,
                top_k=None,
            )
            self._loaded = True
            logger.info(
                "FinBERT pipeline loaded from %s on %s", self._model_path, self._device
            )
        except Exception as e:
            logger.warning("Failed to load FinBERT pipeline: %s", e)
            self._loaded = False

    def classify(self, headlines: list[str]) -> list[SentimentResult]:
        if not self._loaded or self._pipeline is None:
            logger.warning("FinBERT not loaded, skipping classification")
            return []

        raw_results = self._pipeline(headlines, truncation=True, batch_size=8)
        results = []
        for row in raw_results:
            scores = {item["label"]: item["score"] for item in row}
            best = max(row, key=lambda x: x["score"])
            classification = LABEL_MAP.get(best["label"], "Neutral")
            results.append(
                SentimentResult(
                    classification=classification,
                    confidence=best["score"],
                    positive_score=scores.get("positive", 0.0),
                    negative_score=scores.get("negative", 0.0),
                    neutral_score=scores.get("neutral", 0.0),
                )
            )
        return results
