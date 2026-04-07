from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from core.config import AppConfig
from core.logger import get_logger
from core.types import (
    ClarityScore,
    FeatureVector,
    IndicatorResult,
    MacroSentiment,
    OpportunityScore,
    PatternDetectionResult,
    PricePrediction,
    SignalDecision,
    TimeframeAnalysis,
)
from models.explanation_model import ExplanationModel
from models.xgboost_model import XGBoostWrapper

logger = get_logger(__name__)


def weighted_formula(
    indicator_agreement: float,
    max_pattern_confidence: float,
    macro_score: float,
    prediction_confidence: float,
    config: AppConfig,
) -> float:
    abs_macro = min(abs(macro_score), 1.0)
    probability = (
        config.fallback_weight_indicators * indicator_agreement
        + config.fallback_weight_patterns * max_pattern_confidence
        + config.fallback_weight_sentiment * abs_macro
        + config.fallback_weight_prediction * prediction_confidence
    )
    return max(0.0, min(1.0, probability))


def _determine_fallback_direction(
    trend_direction: str,
    prediction_direction: str,
    macro_score: float,
) -> str:
    votes: list[str] = []
    if trend_direction == "bullish":
        votes.append("BUY")
    elif trend_direction == "bearish":
        votes.append("SELL")
    if prediction_direction in ("BUY", "SELL"):
        votes.append(prediction_direction)
    if macro_score > 0:
        votes.append("BUY")
    elif macro_score < 0:
        votes.append("SELL")

    buy_count = votes.count("BUY")
    sell_count = votes.count("SELL")
    if buy_count > sell_count and buy_count > len(votes) / 2:
        return "BUY"
    if sell_count > buy_count and sell_count > len(votes) / 2:
        return "SELL"
    return "NO_TRADE"


def template_explain(
    direction: str,
    probability: float,
    trend_direction: str,
    rsi: float,
    macd_signal: str,
    patterns_summary: str,
    sentiment_summary: str,
    prediction_summary: str,
) -> str:
    parts = [
        f"{direction} signal (probability: {probability:.0%})",
        f"Trend: {trend_direction}, RSI: {rsi:.0f}, MACD: {macd_signal}",
    ]
    if patterns_summary:
        parts.append(f"Patterns: {patterns_summary}")
    if sentiment_summary:
        parts.append(f"Sentiment: {sentiment_summary}")
    if prediction_summary:
        parts.append(f"Prediction: {prediction_summary}")
    return ". ".join(parts)


def assemble_features(
    analysis: TimeframeAnalysis,
    sentiment: MacroSentiment,
    prediction: PricePrediction,
) -> FeatureVector:
    indicators = analysis.indicators
    close = analysis.bars[-1].close

    indicator_features: dict[str, float] = {
        "rsi": indicators.rsi / 100.0,
        "macd_line": indicators.macd_line,
        "macd_signal": indicators.macd_signal,
        "macd_hist": indicators.macd_hist,
        "ema_ratio_20": close / indicators.ema_20 if indicators.ema_20 else 0.0,
        "ema_ratio_50": close / indicators.ema_50 if indicators.ema_50 else 0.0,
        "ema_ratio_200": close / indicators.ema_200 if indicators.ema_200 else 0.0,
        "bb_position": _bb_position(indicators, close),
        "atr_normalized": indicators.atr / close if close else 0.0,
    }

    pattern_features: dict[str, float] = {
        "breakout": 0.0,
        "triangle": 0.0,
        "double_top": 0.0,
        "double_bottom": 0.0,
        "head_shoulders": 0.0,
        "range": 0.0,
    }
    for pat in analysis.patterns.patterns:
        pattern_features[pat.pattern_type] = pat.confidence

    sentiment_features: dict[str, float] = {
        "macro_score": max(-1.0, min(1.0, sentiment.macro_score)),
        "headline_count": float(sentiment.headline_count),
        "is_blackout": 1.0 if sentiment.is_blackout else 0.0,
    }

    direction_map = {"BUY": 1.0, "SELL": -1.0, "NEUTRAL": 0.0}
    prediction_features: dict[str, float] = {
        "direction_encoded": direction_map.get(prediction.direction, 0.0),
        "confidence": prediction.confidence,
        "volatility": prediction.volatility,
        "trend_strength": prediction.trend_strength,
    }

    derived_features: dict[str, float] = {
        "indicator_agreement": analysis.clarity.indicator_agreement,
        "trend_encoded": 1.0
        if indicators.trend_direction == "bullish"
        else (-1.0 if indicators.trend_direction == "bearish" else 0.0),
        "price_vs_support": close / indicators.support if indicators.support else 0.0,
        "price_vs_resistance": close / indicators.resistance
        if indicators.resistance
        else 0.0,
    }

    return FeatureVector(
        indicator_features=indicator_features,
        pattern_features=pattern_features,
        sentiment_features=sentiment_features,
        prediction_features=prediction_features,
        derived_features=derived_features,
    )


def _bb_position(indicators, close: float) -> float:
    bb_range = indicators.bb_upper - indicators.bb_lower
    if bb_range <= 0:
        return 0.5
    return (close - indicators.bb_lower) / bb_range


def compute_opportunity_score(
    analysis: TimeframeAnalysis,
    prediction: PricePrediction,
    sentiment: MacroSentiment,
    signal_direction: str,
    mtf_agreement_fraction: float = 0.0,
) -> OpportunityScore:
    last_close = analysis.bars[-1].close if analysis.bars else 0.0
    atr = analysis.indicators.atr
    if last_close > 0 and atr > 0:
        volatility_regime = min((atr / last_close) / 0.02, 1.0)
    else:
        volatility_regime = 0.0

    if signal_direction == "BUY" and sentiment.macro_score > 0:
        sentiment_alignment = 1.0
    elif signal_direction == "SELL" and sentiment.macro_score < 0:
        sentiment_alignment = 1.0
    else:
        sentiment_alignment = 0.0

    return OpportunityScore(
        trend_strength=prediction.trend_strength,
        volatility_regime=volatility_regime,
        pattern_confidence=analysis.patterns.strongest_confidence,
        prediction_confidence=prediction.confidence,
        sentiment_alignment=sentiment_alignment,
        indicator_agreement=analysis.clarity.indicator_agreement,
        mtf_agreement=mtf_agreement_fraction,
    )


class SignalAgent:
    def __init__(self, config: AppConfig):
        self._config = config
        self._xgboost = XGBoostWrapper(config)
        self._explanation_model = (
            ExplanationModel(config) if config.ollama_enabled else None
        )
        self._recent_decisions: list[tuple[datetime, SignalDecision]] = []

    def decide(
        self,
        analysis: TimeframeAnalysis,
        sentiment: MacroSentiment,
        prediction: PricePrediction,
        mtf_agreement_fraction: float = 0.0,
    ) -> SignalDecision:
        features = assemble_features(analysis, sentiment, prediction)

        if self._xgboost.is_trained():
            probability = self._xgboost.predict(features)
            scoring_method = "xgboost"
            direction = self._determine_xgboost_direction(
                probability, analysis, prediction, sentiment
            )
        else:
            probability = weighted_formula(
                indicator_agreement=analysis.clarity.indicator_agreement,
                max_pattern_confidence=analysis.patterns.strongest_confidence,
                macro_score=sentiment.macro_score,
                prediction_confidence=prediction.confidence,
                config=self._config,
            )
            scoring_method = "fallback"
            direction = _determine_fallback_direction(
                trend_direction=analysis.indicators.trend_direction,
                prediction_direction=prediction.direction,
                macro_score=sentiment.macro_score,
            )

        logger.info(
            "AUDIT scoring: timeframe=%s probability=%.4f method=%s direction=%s "
            "indicator_agreement=%.3f pattern_confidence=%.3f "
            "macro_score=%.3f prediction_confidence=%.3f xgboost_trained=%s",
            analysis.timeframe,
            probability,
            scoring_method,
            direction,
            analysis.clarity.indicator_agreement,
            analysis.patterns.strongest_confidence,
            sentiment.macro_score,
            prediction.confidence,
            self._xgboost.is_trained(),
        )

        if self._config.prediction_agreement_enabled and direction != "NO_TRADE":
            if not self._check_prediction_agreement(direction, prediction):
                return self._make_no_trade(
                    features, analysis, probability, scoring_method
                )

        if self._config.opportunity_score_enabled and direction != "NO_TRADE":
            score = compute_opportunity_score(
                analysis, prediction, sentiment, direction, mtf_agreement_fraction
            )
            if score.composite < self._config.opportunity_score_threshold:
                logger.info(
                    "AUDIT opportunity_score: REJECTED direction=%s composite=%.4f "
                    "threshold=%.2f trend_strength=%.3f volatility_regime=%.3f "
                    "pattern_confidence=%.3f prediction_confidence=%.3f "
                    "sentiment_alignment=%.3f indicator_agreement=%.3f "
                    "mtf_agreement=%.3f",
                    direction,
                    score.composite,
                    self._config.opportunity_score_threshold,
                    score.trend_strength,
                    score.volatility_regime,
                    score.pattern_confidence,
                    score.prediction_confidence,
                    score.sentiment_alignment,
                    score.indicator_agreement,
                    score.mtf_agreement,
                )
                return self._make_no_trade(
                    features, analysis, probability, scoring_method
                )
            logger.info(
                "AUDIT opportunity_score: PASSED direction=%s composite=%.4f",
                direction,
                score.composite,
            )

        if probability < self._config.signal_threshold:
            return self._make_no_trade(features, analysis, probability, scoring_method)

        if direction == "NO_TRADE":
            return self._make_no_trade(features, analysis, probability, scoring_method)

        explanation = self._generate_explanation(
            direction=direction,
            probability=probability,
            scoring_method=scoring_method,
            analysis=analysis,
            sentiment=sentiment,
            prediction=prediction,
        )

        decision = SignalDecision(
            probability=probability,
            direction=direction,
            explanation=explanation,
            scoring_method=scoring_method,
            feature_vector=features,
            timeframe=analysis.timeframe,
            clarity_score=analysis.clarity.composite,
        )

        if not self._is_best_signal(decision):
            return self._make_no_trade(features, analysis, probability, scoring_method)

        self._recent_decisions.append((datetime.now(timezone.utc), decision))
        self._prune_old_decisions()

        logger.info(
            "SignalDecision: %s prob=%.3f method=%s timeframe=%s clarity=%.3f",
            decision.direction,
            decision.probability,
            decision.scoring_method,
            decision.timeframe,
            decision.clarity_score,
        )

        return decision

    def _check_prediction_agreement(
        self, direction: str, prediction: PricePrediction
    ) -> bool:
        if prediction.confidence == 0.0 and prediction.direction == "NEUTRAL":
            logger.info(
                "AUDIT prediction_agreement: bypassed (LSTM unavailable) "
                "signal_direction=%s prediction_direction=%s prediction_confidence=%.4f",
                direction,
                prediction.direction,
                prediction.confidence,
            )
            return True
        if prediction.direction == direction:
            return True
        logger.info(
            "AUDIT prediction_agreement: REJECTED signal_direction=%s "
            "prediction_direction=%s prediction_confidence=%.4f",
            direction,
            prediction.direction,
            prediction.confidence,
        )
        return False

    def _generate_explanation(
        self,
        direction: str,
        probability: float,
        scoring_method: str,
        analysis: TimeframeAnalysis,
        sentiment: MacroSentiment,
        prediction: PricePrediction,
    ) -> str:
        try:
            ollama_result = self._explanation_model.explain(
                decision=SignalDecision(
                    probability=probability,
                    direction=direction,
                    explanation="",
                    scoring_method=scoring_method,
                    feature_vector=FeatureVector(),
                    timeframe=analysis.timeframe,
                    clarity_score=analysis.clarity.composite,
                ),
                indicators=analysis.indicators,
                sentiment=sentiment,
                prediction_direction=prediction.direction,
                prediction_confidence=prediction.confidence,
                patterns_summary=_patterns_summary(analysis.patterns),
            )
            if ollama_result:
                return ollama_result
        except Exception as e:
            logger.warning("Ollama explanation failed, using template: %s", e)

        return template_explain(
            direction=direction,
            probability=probability,
            trend_direction=analysis.indicators.trend_direction,
            rsi=analysis.indicators.rsi,
            macd_signal=_macd_signal_desc(analysis.indicators.macd_hist),
            patterns_summary=_patterns_summary(analysis.patterns),
            sentiment_summary=_sentiment_summary(sentiment),
            prediction_summary=_prediction_summary(prediction),
        )

    def _determine_xgboost_direction(
        self,
        probability: float,
        analysis: TimeframeAnalysis,
        prediction: PricePrediction,
        sentiment: MacroSentiment,
    ) -> str:
        return _determine_fallback_direction(
            trend_direction=analysis.indicators.trend_direction,
            prediction_direction=prediction.direction,
            macro_score=sentiment.macro_score,
        )

    def _make_no_trade(
        self,
        features: FeatureVector,
        analysis: TimeframeAnalysis,
        probability: float,
        scoring_method: str,
    ) -> SignalDecision:
        return SignalDecision(
            probability=probability,
            direction="NO_TRADE",
            explanation="",
            scoring_method=scoring_method,
            feature_vector=features,
            timeframe=analysis.timeframe,
            clarity_score=analysis.clarity.composite,
        )

    def _is_best_signal(self, decision: SignalDecision) -> bool:
        now = datetime.now(timezone.utc)
        window_minutes = self._config.decision_window_minutes

        for ts, recent in self._recent_decisions:
            age = (now - ts).total_seconds() / 60.0
            if age < window_minutes:
                if recent.probability >= decision.probability:
                    logger.info(
                        "AUDIT signal_suppressed: new_direction=%s new_prob=%.4f "
                        "suppressed_by_direction=%s suppressed_by_prob=%.4f "
                        "suppressed_by_timeframe=%s age_minutes=%.1f window=%d",
                        decision.direction,
                        decision.probability,
                        recent.direction,
                        recent.probability,
                        recent.timeframe,
                        age,
                        window_minutes,
                    )
                    return False

        return True

    def _prune_old_decisions(self) -> None:
        now = datetime.now(timezone.utc)
        window_minutes = self._config.decision_window_minutes
        self._recent_decisions = [
            entry
            for entry in self._recent_decisions
            if (now - entry[0]).total_seconds() / 60.0 < window_minutes
        ]


def _macd_signal_desc(macd_hist: float) -> str:
    if macd_hist > 0:
        return "bullish crossover"
    elif macd_hist < 0:
        return "bearish crossover"
    return "neutral"


def _patterns_summary(patterns: PatternDetectionResult) -> str:
    if not patterns.patterns:
        return "none detected"
    parts = [f"{p.pattern_type}({p.confidence:.0%})" for p in patterns.patterns]
    return ", ".join(parts)


def _sentiment_summary(sentiment: MacroSentiment) -> str:
    return f"score={sentiment.macro_score:+.2f}, headlines={sentiment.headline_count}"


def _prediction_summary(prediction: PricePrediction) -> str:
    return f"{prediction.direction} ({prediction.confidence:.0%} confidence)"
