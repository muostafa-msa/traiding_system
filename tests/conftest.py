from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.config import AppConfig
from core.types import (
    OHLCBar,
    TradeSignal,
    PatternResult,
    PatternDetectionResult,
    PricePrediction,
    MacroSentiment,
    FeatureVector,
    TimeframeAnalysis,
    ClarityScore,
    IndicatorResult,
)
from models.model_manager import ModelManager
from storage.database import Database


def _default_sentiment_fields():
    return dict(
        rss_feed_urls="",
        rss_keywords="gold,inflation,fed",
        blackout_keywords="fed,fomc,nfp",
        blackout_duration_hours=4.0,
        sentiment_window_hours=4.0,
        finbert_model_path="models/finbert",
        model_device="auto",
        lstm_model_path="models/lstm",
        xgboost_model_path="/tmp/nonexistent_xgboost_test",
        ollama_base_url="http://localhost:11434",
        ollama_model="gpt-oss:20b",
        ollama_enabled=False,
        fallback_weight_indicators=0.30,
        fallback_weight_patterns=0.20,
        fallback_weight_sentiment=0.25,
        fallback_weight_prediction=0.25,
        explanation_max_tokens=150,
        explanation_temperature=0.7,
        lstm_sequence_length=60,
        lstm_direction_threshold=0.15,
        decision_window_minutes=15,
        prediction_agreement_enabled=True,
        mtf_confirmation_enabled=True,
        mtf_min_agreeing_timeframes=2,
        opportunity_score_enabled=True,
        opportunity_score_threshold=0.55,
    )


@pytest.fixture
def test_config() -> AppConfig:
    return AppConfig(
        market_data_provider="twelvedata",
        market_data_api_key="test_key",
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
        **_default_sentiment_fields(),
    )


@pytest.fixture
def db(test_config: AppConfig) -> Database:
    return Database(test_config)


@pytest.fixture
def sample_bars() -> list[OHLCBar]:
    bars = []
    base = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    for i in range(250):
        bars.append(
            OHLCBar(
                timestamp=base,
                open=2300.0 + i * 0.5,
                high=2302.0 + i * 0.5,
                low=2298.0 + i * 0.5,
                close=2301.0 + i * 0.5,
                volume=1000.0,
            )
        )
    return bars


@pytest.fixture
def sample_buy_signal() -> TradeSignal:
    return TradeSignal(
        asset="XAU/USD",
        direction="BUY",
        entry_price=2350.0,
        stop_loss=2335.0,
        take_profit=2380.0,
        probability=0.85,
        reasoning="Strong bullish momentum",
        timeframe="1h",
        timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_sell_signal() -> TradeSignal:
    return TradeSignal(
        asset="XAU/USD",
        direction="SELL",
        entry_price=2350.0,
        stop_loss=2365.0,
        take_profit=2320.0,
        probability=0.75,
        reasoning="Bearish reversal pattern",
        timeframe="1h",
        timestamp=datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_indicator_result() -> IndicatorResult:
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


@pytest.fixture
def sample_pattern_detection_result() -> PatternDetectionResult:
    breakout = PatternResult(
        pattern_type="breakout",
        confidence=0.75,
        direction="BUY",
        price_level=2330.0,
    )
    return PatternDetectionResult(
        patterns=[breakout],
        strongest_confidence=0.75,
        strongest_direction="BUY",
    )


@pytest.fixture
def sample_price_prediction() -> PricePrediction:
    return PricePrediction(
        direction="BUY",
        confidence=0.65,
        volatility=0.015,
        trend_strength=0.7,
        horizon_bars=12,
    )


@pytest.fixture
def sample_macro_sentiment() -> MacroSentiment:
    return MacroSentiment(
        macro_score=0.3,
        headline_count=5,
        sentiments=[],
        is_blackout=False,
    )


@pytest.fixture
def sample_feature_vector() -> FeatureVector:
    return FeatureVector(
        indicator_features={
            "rsi": 55.0,
            "macd_line": 0.5,
            "macd_signal": 0.3,
            "macd_hist": 0.2,
            "ema_ratio_20": 1.004,
            "ema_ratio_50": 1.009,
            "ema_ratio_200": 1.017,
            "bb_position": 0.5,
            "atr_normalized": 0.006,
        },
        pattern_features={
            "breakout": 0.75,
            "triangle": 0.0,
            "double_top": 0.0,
            "double_bottom": 0.0,
            "head_shoulders": 0.0,
            "range": 0.0,
        },
        sentiment_features={
            "macro_score": 0.3,
            "headline_count": 5.0,
            "is_blackout": 0.0,
        },
        prediction_features={
            "direction_encoded": 1.0,
            "confidence": 0.65,
            "volatility": 0.015,
            "trend_strength": 0.7,
        },
        derived_features={
            "indicator_agreement": 0.75,
            "trend_encoded": 1.0,
            "price_vs_support": 1.009,
            "price_vs_resistance": 0.991,
        },
    )


@pytest.fixture
def sample_clarity_score() -> ClarityScore:
    return ClarityScore(
        timeframe="1h",
        indicator_agreement=0.75,
        pattern_confidence=0.6,
        data_completeness=0.95,
    )


@pytest.fixture
def sample_timeframe_analysis(
    sample_indicator_result: IndicatorResult,
    sample_pattern_detection_result: PatternDetectionResult,
    sample_clarity_score: ClarityScore,
    sample_bars: list[OHLCBar],
) -> TimeframeAnalysis:
    return TimeframeAnalysis(
        timeframe="1h",
        indicators=sample_indicator_result,
        patterns=sample_pattern_detection_result,
        clarity=sample_clarity_score,
        bars=sample_bars,
        timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def mock_model_manager(test_config: AppConfig) -> ModelManager:
    return ModelManager(test_config)
