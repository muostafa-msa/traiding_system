from __future__ import annotations

import importlib
import time

from core.config import AppConfig
from core.logger import get_logger

logger = get_logger(__name__)


def _get_torch():
    return importlib.import_module("torch")


def _get_auto_model():
    mod = importlib.import_module("transformers")
    return mod.AutoModelForSequenceClassification


def _get_auto_tokenizer():
    mod = importlib.import_module("transformers")
    return mod.AutoTokenizer


class ModelManager:
    def __init__(self, config: AppConfig):
        self._config = config
        self._models: dict[str, tuple] = {}
        self._device: str | None = None

    def detect_device(self) -> str:
        if self._device is not None:
            return self._device

        override = self._config.model_device.lower()
        if override in ("cpu", "cuda", "mps"):
            self._device = override
            logger.info("Device override: %s", self._device)
            return self._device

        torch = _get_torch()
        if torch.cuda.is_available():
            self._device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self._device = "mps"
        else:
            self._device = "cpu"

        logger.info("Auto-detected device: %s", self._device)
        return self._device

    def load_model(self, name: str, path: str) -> None:
        if name in self._models:
            logger.debug("Model '%s' already loaded, using cache", name)
            return

        device_str = self.detect_device()
        start = time.time()

        AutoModelForSequenceClassification = _get_auto_model()
        AutoTokenizer = _get_auto_tokenizer()

        model = AutoModelForSequenceClassification.from_pretrained(path)
        tokenizer = AutoTokenizer.from_pretrained(path)

        if device_str == "cuda":
            model = model.to("cuda")
        elif device_str == "mps":
            model = model.to("mps")

        model.eval()
        self._models[name] = (model, tokenizer)
        elapsed = time.time() - start
        logger.info("Model '%s' loaded on %s in %.1fs", name, device_str, elapsed)

    def get_model(self, name: str):
        entry = self._models.get(name)
        if entry is None:
            return None
        return entry[0]

    def get_tokenizer(self, name: str):
        entry = self._models.get(name)
        if entry is None:
            return None
        return entry[1]
