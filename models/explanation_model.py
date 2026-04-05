from __future__ import annotations

import requests

from core.config import AppConfig
from core.logger import get_logger
from core.types import IndicatorResult, MacroSentiment, SignalDecision

logger = get_logger(__name__)

PROMPT_TEMPLATE = """Market Analysis Summary:
Asset: XAU/USD | Direction: {direction} | Confidence: {probability:.0%}
Technical: {trend_direction} trend, RSI={rsi:.0f}, MACD {macd_signal}
Patterns: {patterns_summary}
Sentiment: {sentiment_summary} (score: {macro_score:+.2f})
Prediction: {prediction_direction} with {prediction_confidence:.0%} confidence

Explain why this is a {direction} opportunity:
"""


def build_prompt(
    direction: str,
    probability: float,
    trend_direction: str,
    rsi: float,
    macd_signal: str,
    patterns_summary: str,
    sentiment_summary: str,
    macro_score: float,
    prediction_direction: str,
    prediction_confidence: float,
) -> str:
    return PROMPT_TEMPLATE.format(
        direction=direction,
        probability=probability,
        trend_direction=trend_direction,
        rsi=rsi,
        macd_signal=macd_signal,
        patterns_summary=patterns_summary,
        sentiment_summary=sentiment_summary,
        macro_score=macro_score,
        prediction_direction=prediction_direction,
        prediction_confidence=prediction_confidence,
    )


class ExplanationModel:
    def __init__(self, config: AppConfig):
        self._config = config
        self._base_url = config.ollama_base_url.rstrip("/")
        self._model = config.ollama_model

    def explain(
        self,
        decision: SignalDecision,
        indicators: IndicatorResult,
        sentiment: MacroSentiment,
        prediction_direction: str = "NEUTRAL",
        prediction_confidence: float = 0.0,
        patterns_summary: str = "none detected",
    ) -> str | None:
        macd_signal = (
            "bullish crossover"
            if indicators.macd_hist > 0
            else ("bearish crossover" if indicators.macd_hist < 0 else "neutral")
        )

        prompt = build_prompt(
            direction=decision.direction,
            probability=decision.probability,
            trend_direction=indicators.trend_direction,
            rsi=indicators.rsi,
            macd_signal=macd_signal,
            patterns_summary=patterns_summary,
            sentiment_summary=f"score={sentiment.macro_score:+.2f}, headlines={sentiment.headline_count}",
            macro_score=sentiment.macro_score,
            prediction_direction=prediction_direction,
            prediction_confidence=prediction_confidence,
        )

        try:
            response = requests.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "options": {
                        "temperature": self._config.explanation_temperature,
                        "num_predict": self._config.explanation_max_tokens,
                    },
                    "stream": False,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            explanation = data.get("response", "").strip()
            if explanation:
                logger.info("GPT-OSS explanation generated (%d chars)", len(explanation))
                return explanation
            return None
        except Exception as e:
            logger.warning("GPT-OSS explanation failed: %s", e)
            return None
