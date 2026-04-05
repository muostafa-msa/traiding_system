from __future__ import annotations

from core.config import AppConfig
from core.logger import get_logger
from core.types import IndicatorResult, OHLCBar, PricePrediction
from models.lstm_model import LSTMWrapper
from models.model_manager import ModelManager

logger = get_logger(__name__)


class PredictionAgent:
    def __init__(self, config: AppConfig, model_manager: ModelManager):
        self._config = config
        self._lstm = LSTMWrapper(config, model_manager)

    def predict(
        self, bars: list[OHLCBar], indicators: IndicatorResult
    ) -> PricePrediction:
        try:
            prediction = self._lstm.predict(bars, indicators)
            logger.info(
                "Prediction: direction=%s confidence=%.3f volatility=%.4f trend_strength=%.3f",
                prediction.direction,
                prediction.confidence,
                prediction.volatility,
                prediction.trend_strength,
            )
            return prediction
        except Exception as e:
            logger.warning("PredictionAgent failed, returning neutral: %s", e)
            return PricePrediction(
                direction="NEUTRAL",
                confidence=0.0,
                volatility=0.0,
                trend_strength=0.0,
                horizon_bars=12,
            )
