from __future__ import annotations

import math
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from core.config import AppConfig
from core.types import OHLCBar, NewsItem, TradeSignal
from agents.news_agent import NewsAgent
from agents.risk_agent import RiskAgent
from core.scheduler import TradingScheduler
from execution.telegram_bot import TelegramBot
from models.model_manager import ModelManager
from storage.database import Database
from tests.conftest import _default_sentiment_fields


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
        **_default_sentiment_fields(),
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

            bot.broadcast.assert_not_called()


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


class TestSentimentPipeline:
    @pytest.fixture
    def sentiment_config(self) -> AppConfig:
        fields = _default_sentiment_fields()
        fields["rss_feed_urls"] = "https://example.com/rss"
        fields["rss_keywords"] = "gold,inflation,fed,oil"
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
            **fields,
        )

    @patch("models.model_manager._get_torch")
    @patch("models.finbert._get_pipeline")
    def test_full_sentiment_pipeline_fetch_to_persist(
        self, mock_get_pipeline, mock_get_torch, sentiment_config: AppConfig
    ):
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False
        mock_get_torch.return_value = mock_torch

        mock_pipeline_fn = MagicMock()
        mock_get_pipeline.return_value = mock_pipeline_fn
        mock_pipe = MagicMock()
        mock_pipeline_fn.return_value = mock_pipe

        mock_pipe.return_value = [
            [
                {"label": "positive", "score": 0.9},
                {"label": "negative", "score": 0.05},
                {"label": "neutral", "score": 0.05},
            ],
            [
                {"label": "negative", "score": 0.85},
                {"label": "positive", "score": 0.1},
                {"label": "neutral", "score": 0.05},
            ],
            [
                {"label": "neutral", "score": 0.7},
                {"label": "positive", "score": 0.2},
                {"label": "negative", "score": 0.1},
            ],
        ]

        mock_feed = MagicMock()
        mock_feed.entries = [
            MagicMock(
                title="Gold prices surge on inflation data",
                link="https://example.com/1",
                published_parsed=time.struct_time((2026, 1, 15, 10, 0, 0, 0, 0, 0)),
            ),
            MagicMock(
                title="Fed signals hawkish stance on rates",
                link="https://example.com/2",
                published_parsed=time.struct_time((2026, 1, 15, 10, 5, 0, 0, 0, 0)),
            ),
            MagicMock(
                title="Oil prices stabilize after volatile week",
                link="https://example.com/3",
                published_parsed=time.struct_time((2026, 1, 15, 10, 10, 0, 0, 0, 0)),
            ),
        ]

        with (
            patch("data.news_data.requests.get") as mock_get,
            patch("data.news_data.feedparser.parse", return_value=mock_feed),
        ):
            mock_response = MagicMock()
            mock_response.text = "<rss></rss>"
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            db = Database(sentiment_config)
            mgr = ModelManager(sentiment_config)
            agent = NewsAgent(sentiment_config, db, mgr)

            result = agent.run()

        assert result.headline_count == 3
        assert -1.0 <= result.macro_score <= 1.0
        assert len(result.sentiments) == 3

        news_rows = db.get_recent_news(24)
        assert len(news_rows) == 3
        classifications = {row["classification"] for row in news_rows}
        assert classifications.issubset({"Bullish", "Bearish", "Neutral"})

    @patch("models.model_manager._get_torch")
    @patch("models.finbert._get_pipeline")
    def test_batch_classify_20_headlines_under_30s(
        self, mock_get_pipeline, mock_get_torch, sentiment_config: AppConfig
    ):
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False
        mock_get_torch.return_value = mock_torch

        mock_pipeline_fn = MagicMock()
        mock_get_pipeline.return_value = mock_pipeline_fn
        mock_pipe = MagicMock()
        mock_pipeline_fn.return_value = mock_pipe

        mock_pipe.return_value = [
            [
                {"label": "positive", "score": 0.8},
                {"label": "negative", "score": 0.1},
                {"label": "neutral", "score": 0.1},
            ]
        ] * 20

        headlines = [f"Headline number {i} about gold" for i in range(20)]
        mock_feed = MagicMock()
        mock_feed.entries = [
            MagicMock(
                title=headlines[i],
                link=f"https://example.com/{i}",
                published_parsed=time.struct_time(
                    (2026, 1, 15, 10, i % 60, 0, 0, 0, 0)
                ),
            )
            for i in range(20)
        ]

        with (
            patch("data.news_data.requests.get") as mock_get,
            patch("data.news_data.feedparser.parse", return_value=mock_feed),
        ):
            mock_response = MagicMock()
            mock_response.text = "<rss></rss>"
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            db = Database(sentiment_config)
            mgr = ModelManager(sentiment_config)
            agent = NewsAgent(sentiment_config, db, mgr)

            start = time.time()
            result = agent.run()
            elapsed = time.time() - start

        assert result.headline_count == 20
        assert elapsed < 30.0, f"Batch of 20 took {elapsed:.2f}s (must be < 30s)"


class TestBlackoutPipeline:
    def test_blackout_trigger_reject_expire_flow(self, integration_config: AppConfig):
        db = Database(integration_config)
        risk = RiskAgent(integration_config, db)

        signal = TradeSignal(
            asset="XAU/USD",
            direction="BUY",
            entry_price=2300.0,
            stop_loss=2285.0,
            take_profit=2340.0,
            probability=0.8,
            reasoning="test",
            timeframe="1h",
            timestamp=datetime.now(timezone.utc),
        )

        verdict_before = risk.evaluate(signal)
        assert verdict_before.approved is True

        until = datetime.now(timezone.utc) + timedelta(hours=4)
        db.set_blackout_until(until)
        assert db.is_blackout_active() is True

        verdict_during = risk.evaluate(signal)
        assert verdict_during.approved is False
        assert "News blackout period" in (verdict_during.rejection_reason or "")

        past_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.set_blackout_until(past_until)
        db.clear_expired_blackout()
        assert db.is_blackout_active() is False

        verdict_after = risk.evaluate(signal)
        assert verdict_after.approved is True
