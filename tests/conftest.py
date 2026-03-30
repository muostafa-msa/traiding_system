from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.config import AppConfig
from core.types import OHLCBar, TradeSignal
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
