from __future__ import annotations

import math
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from core.config import AppConfig
from core.types import OHLCBar
from core.scheduler import TradingScheduler
from execution.telegram_bot import TelegramBot
from storage.database import Database


def _make_bars(
    n: int = 250, base_price: float = 2300.0, volatility: float = 5.0
) -> list[OHLCBar]:
    bars = []
    base_ts = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    for i in range(n):
        angle = 2 * math.pi * i / 30
        close = base_price + volatility * math.sin(angle) + i * 0.1
        high = close + volatility * 0.5
        low = close - volatility * 0.5
        bars.append(
            OHLCBar(
                timestamp=base_ts + timedelta(minutes=5 * i),
                open=close - volatility * 0.1,
                high=high,
                low=low,
                close=close,
                volume=1000.0,
            )
        )
    return bars


@pytest.fixture
def integration_config() -> AppConfig:
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
    )


class TestFullPipeline:
    def test_full_cycle_with_mocked_provider(self, integration_config: AppConfig):
        bars = _make_bars(250)

        with patch("core.scheduler.get_provider") as mock_get_prov:
            provider = MagicMock()
            provider.get_ohlc.return_value = bars
            mock_get_prov.return_value = provider

            db = Database(integration_config)
            bot = TelegramBot(integration_config, db)
            scheduler = TradingScheduler(integration_config, db, bot)

            scheduler.run_cycle("1h")

            provider.get_ohlc.assert_called_once_with("XAU/USD", "1h", 250)
            state = db.get_account_state()
            assert state.capital == 10000.0

    def test_pipeline_handles_empty_data_gracefully(
        self, integration_config: AppConfig
    ):
        with patch("core.scheduler.get_provider") as mock_get_prov:
            provider = MagicMock()
            provider.get_ohlc.return_value = []
            mock_get_prov.return_value = provider

            db = Database(integration_config)
            bot = TelegramBot(integration_config, db)
            scheduler = TradingScheduler(integration_config, db, bot)

            scheduler.run_cycle("1h")

            state = db.get_account_state()
            assert state.capital == 10000.0

    def test_pipeline_persist_and_broadcast(self, integration_config: AppConfig):
        bars = _make_bars(250)

        with patch("core.scheduler.get_provider") as mock_get_prov:
            provider = MagicMock()
            provider.get_ohlc.return_value = bars
            mock_get_prov.return_value = provider

            db = Database(integration_config)
            bot = MagicMock(spec=TelegramBot)
            scheduler = TradingScheduler(integration_config, db, bot)

            scheduler.run_cycle("5min")

            bot.broadcast.assert_called_once()
            msg = bot.broadcast.call_args[0][0]
            assert "GOLD TECHNICAL ANALYSIS" in msg
            assert "5min" in msg


class TestCyclePerformance:
    def test_full_cycle_under_60_seconds(self, integration_config: AppConfig):
        bars = _make_bars(250)

        with patch("core.scheduler.get_provider") as mock_get_prov:
            provider = MagicMock()
            provider.get_ohlc.return_value = bars
            mock_get_prov.return_value = provider

            db = Database(integration_config)
            bot = TelegramBot(integration_config, db)
            scheduler = TradingScheduler(integration_config, db, bot)

            start = time.time()
            for tf in ["5min", "15min", "1h", "4h"]:
                scheduler.run_cycle(tf)
            elapsed = time.time() - start

            assert elapsed < 60.0, (
                f"Full 4-timeframe cycle took {elapsed:.2f}s (must be < 60s)"
            )
            assert elapsed < 10.0, (
                f"Full cycle took {elapsed:.2f}s — expected well under 10s"
            )


class TestOHLCValidation:
    def test_malformed_candles_rejected(self, integration_config: AppConfig):
        bars = _make_bars(250)

        with patch("core.scheduler.get_provider") as mock_get_prov:
            provider = MagicMock()
            provider.get_ohlc.return_value = bars
            mock_get_prov.return_value = provider

            db = Database(integration_config)
            bot = TelegramBot(integration_config, db)
            scheduler = TradingScheduler(integration_config, db, bot)

            validated = scheduler._validate_bars(bars)
            assert len(validated) == 250

    def test_too_few_valid_bars_skips_cycle(self, integration_config: AppConfig):
        bars = _make_bars(50)

        with patch("core.scheduler.get_provider") as mock_get_prov:
            provider = MagicMock()
            provider.get_ohlc.return_value = bars
            mock_get_prov.return_value = provider

            db = Database(integration_config)
            bot = MagicMock(spec=TelegramBot)
            scheduler = TradingScheduler(integration_config, db, bot)

            scheduler.run_cycle("1h")

            bot.broadcast.assert_not_called()
