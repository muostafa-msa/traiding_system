from __future__ import annotations

import hashlib
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from core.config import AppConfig
from core.types import MacroSentiment, NewsItem, SentimentResult
from data.news_data import NewsCollector
from storage.database import Database
from tests.conftest import _default_sentiment_fields


def _make_config(**overrides) -> AppConfig:
    defaults = dict(
        market_data_provider="twelvedata",
        market_data_api_key="test",
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
    defaults.update(overrides)
    return AppConfig(**defaults)


def _make_item(headline: str = "Gold prices surge") -> NewsItem:
    return NewsItem(
        source="test",
        headline=headline,
        url="https://example.com",
        published_at=datetime.now(timezone.utc),
    )


class TestNewsCollectorRSSFetch:
    @patch("data.news_data.feedparser")
    @patch("data.news_data.requests")
    def test_fetch_headlines_returns_items(self, mock_requests, mock_fp):
        mock_response = MagicMock()
        mock_response.text = "<rss>...</rss>"
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response

        mock_fp.parse.return_value = MagicMock(
            bozo=False,
            entries=[
                MagicMock(
                    title="Gold prices surge",
                    link="https://a.com",
                    published_parsed=None,
                ),
            ],
        )

        collector = NewsCollector(
            feed_urls=["https://example.com/rss"],
            keywords=["gold"],
        )
        items = collector.fetch_headlines()
        assert len(items) == 1
        assert items[0].headline == "Gold prices surge"

    @patch("data.news_data.requests")
    def test_fetch_headlines_handles_feed_failure(self, mock_requests):
        mock_requests.get.side_effect = Exception("network error")
        collector = NewsCollector(
            feed_urls=["https://bad-feed.com/rss"],
            keywords=["gold"],
        )
        items = collector.fetch_headlines()
        assert items == []

    @patch("data.news_data.feedparser")
    @patch("data.news_data.requests")
    def test_fetch_headlines_empty_feed(self, mock_requests, mock_fp):
        mock_response = MagicMock()
        mock_response.text = "<rss></rss>"
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        mock_fp.parse.return_value = MagicMock(bozo=False, entries=[])

        collector = NewsCollector(
            feed_urls=["https://example.com/rss"],
            keywords=["gold"],
        )
        items = collector.fetch_headlines()
        assert items == []


class TestNewsCollectorKeywordFilter:
    @patch("data.news_data.feedparser")
    @patch("data.news_data.requests")
    def test_keyword_match_included(self, mock_requests, mock_fp):
        mock_response = MagicMock()
        mock_response.text = "<rss>...</rss>"
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        mock_fp.parse.return_value = MagicMock(
            bozo=False,
            entries=[
                MagicMock(
                    title="Gold prices surge",
                    link="https://a.com",
                    published_parsed=None,
                ),
            ],
        )

        collector = NewsCollector(
            feed_urls=["https://example.com/rss"],
            keywords=["gold"],
        )
        items = collector.fetch_headlines()
        assert len(items) == 1

    @patch("data.news_data.feedparser")
    @patch("data.news_data.requests")
    def test_no_keyword_match_excluded(self, mock_requests, mock_fp):
        mock_response = MagicMock()
        mock_response.text = "<rss>...</rss>"
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        mock_fp.parse.return_value = MagicMock(
            bozo=False,
            entries=[
                MagicMock(
                    title="Weather report for today",
                    link="https://a.com",
                    published_parsed=None,
                ),
            ],
        )

        collector = NewsCollector(
            feed_urls=["https://example.com/rss"],
            keywords=["gold"],
        )
        items = collector.fetch_headlines()
        assert len(items) == 0

    @patch("data.news_data.feedparser")
    @patch("data.news_data.requests")
    def test_keyword_case_insensitive(self, mock_requests, mock_fp):
        mock_response = MagicMock()
        mock_response.text = "<rss>...</rss>"
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        mock_fp.parse.return_value = MagicMock(
            bozo=False,
            entries=[
                MagicMock(
                    title="GOLD PRICES SURGE",
                    link="https://a.com",
                    published_parsed=None,
                ),
            ],
        )

        collector = NewsCollector(
            feed_urls=["https://example.com/rss"],
            keywords=["gold"],
        )
        items = collector.fetch_headlines()
        assert len(items) == 1


class TestNewsCollectorDedup:
    def test_sha256_dedup_removes_duplicates(self):
        collector = NewsCollector(feed_urls=[], keywords=["gold"])
        item1 = _make_item("Gold prices surge")
        item2 = _make_item("Gold prices surge")
        combined = collector._deduplicate([item1, item2])
        assert len(combined) == 1


class TestSentimentAgent:
    def test_classify_returns_same_length(self):
        from agents.sentiment_agent import SentimentAgent

        config = _make_config()
        mock_mm = MagicMock()
        agent = SentimentAgent(config, mock_mm)
        mock_results = [
            SentimentResult(
                classification="Bullish",
                confidence=0.9,
                positive_score=0.9,
                negative_score=0.05,
                neutral_score=0.05,
            ),
            SentimentResult(
                classification="Bearish",
                confidence=0.8,
                positive_score=0.10,
                negative_score=0.80,
                neutral_score=0.10,
            ),
        ]
        agent._finbert = MagicMock()
        agent._finbert._loaded = True
        agent._finbert.classify.return_value = mock_results

        items = [_make_item("Gold up"), _make_item("Fed raises rates")]
        results = agent.classify(items)
        assert len(results) == 2

    def test_classify_returns_empty_when_model_unavailable(self):
        from agents.sentiment_agent import SentimentAgent

        config = _make_config()
        mock_mm = MagicMock()
        mock_mm.detect_device.return_value = "cpu"
        agent = SentimentAgent(config, mock_mm)
        agent._ensure_model = lambda: None

        items = [_make_item("Gold up")]
        results = agent.classify(items)
        assert results == []


class TestNewsAgent:
    def test_run_returns_macro_sentiment(self):
        from agents.news_agent import NewsAgent

        config = _make_config(rss_feed_urls="https://example.com/rss")
        db = Database(config)
        mock_mm = MagicMock()

        agent = NewsAgent(config, db, mock_mm)
        agent._collector = MagicMock()
        agent._collector.fetch_headlines.return_value = [
            _make_item("Gold prices surge"),
        ]
        agent._sentiment_agent = MagicMock()
        agent._sentiment_agent.classify.return_value = [
            SentimentResult(
                classification="Bullish",
                confidence=0.9,
                positive_score=0.9,
                negative_score=0.05,
                neutral_score=0.05,
            ),
        ]

        result = agent.run()
        assert isinstance(result, MacroSentiment)
        assert result.headline_count == 1

    def test_run_empty_headlines_returns_zero_score(self):
        from agents.news_agent import NewsAgent

        config = _make_config(rss_feed_urls="https://example.com/rss")
        db = Database(config)
        mock_mm = MagicMock()

        agent = NewsAgent(config, db, mock_mm)
        agent._collector = MagicMock()
        agent._collector.fetch_headlines.return_value = []
        agent._sentiment_agent = MagicMock()

        result = agent.run()
        assert result.macro_score == 0.0
        assert result.headline_count == 0
        assert result.is_blackout is False

    def test_run_persists_to_database(self):
        from agents.news_agent import NewsAgent

        config = _make_config(rss_feed_urls="https://example.com/rss")
        db = Database(config)
        mock_mm = MagicMock()

        agent = NewsAgent(config, db, mock_mm)
        agent._collector = MagicMock()
        agent._collector.fetch_headlines.return_value = [
            _make_item("Gold prices surge"),
        ]
        agent._sentiment_agent = MagicMock()
        agent._sentiment_agent.classify.return_value = [
            SentimentResult(
                classification="Bullish",
                confidence=0.9,
                positive_score=0.9,
                negative_score=0.05,
                neutral_score=0.05,
            ),
        ]

        agent.run()
        rows = db.get_recent_news(4)
        assert len(rows) == 1
        assert rows[0]["classification"] == "Bullish"

    def test_macro_score_calculation(self):
        from agents.news_agent import NewsAgent

        config = _make_config(rss_feed_urls="https://example.com/rss")
        db = Database(config)
        mock_mm = MagicMock()

        agent = NewsAgent(config, db, mock_mm)
        agent._collector = MagicMock()
        agent._collector.fetch_headlines.return_value = [
            _make_item("Gold prices surge"),
            _make_item("Fed raises rates"),
        ]
        agent._sentiment_agent = MagicMock()
        agent._sentiment_agent.classify.return_value = [
            SentimentResult(
                classification="Bullish",
                confidence=0.8,
                positive_score=0.8,
                negative_score=0.1,
                neutral_score=0.1,
            ),
            SentimentResult(
                classification="Bearish",
                confidence=0.6,
                positive_score=0.1,
                negative_score=0.6,
                neutral_score=0.3,
            ),
        ]

        result = agent.run()
        expected = (1.0 * 0.8 + (-1.0) * 0.6) / 2
        assert abs(result.macro_score - expected) < 0.001


class TestBlackoutKeywordDetection:
    def _make_news_agent(self, headlines):
        from agents.news_agent import NewsAgent

        config = _make_config(
            rss_feed_urls="https://example.com/rss",
            blackout_keywords="fed,fomc,nfp,non-farm,cpi,consumer price,interest rate decision",
            blackout_duration_hours=4.0,
        )
        db = Database(config)
        mock_mm = MagicMock()
        agent = NewsAgent(config, db, mock_mm)
        agent._collector = MagicMock()
        agent._collector.fetch_headlines.return_value = [
            _make_item(h) for h in headlines
        ]
        agent._sentiment_agent = MagicMock()
        agent._sentiment_agent.classify.return_value = [
            SentimentResult(
                classification="Bearish",
                confidence=0.9,
                positive_score=0.05,
                negative_score=0.9,
                neutral_score=0.05,
            )
            for _ in headlines
        ]
        return agent, db

    def test_fed_keyword_triggers_blackout(self):
        agent, db = self._make_news_agent(["Fed signals rate hike ahead"])
        agent.run()
        assert db.is_blackout_active() is True

    def test_fomc_keyword_triggers_blackout(self):
        agent, db = self._make_news_agent(["FOMC meeting results announced"])
        agent.run()
        assert db.is_blackout_active() is True

    def test_nfp_keyword_triggers_blackout(self):
        agent, db = self._make_news_agent(["NFP data shows strong jobs growth"])
        agent.run()
        assert db.is_blackout_active() is True

    def test_non_trigger_headline_no_blackout(self):
        agent, db = self._make_news_agent(["Gold prices steady in Asia trading"])
        agent.run()
        assert db.is_blackout_active() is False

    def test_keyword_case_insensitive(self):
        agent, db = self._make_news_agent(["FED RAISES RATES"])
        agent.run()
        assert db.is_blackout_active() is True


class TestBlackoutAutoExpiry:
    def test_expired_blackout_cleared_on_run(self):
        from agents.news_agent import NewsAgent

        config = _make_config(
            rss_feed_urls="https://example.com/rss",
            blackout_keywords="fed",
            blackout_duration_hours=4.0,
        )
        db = Database(config)
        mock_mm = MagicMock()
        agent = NewsAgent(config, db, mock_mm)
        agent._collector = MagicMock()
        agent._collector.fetch_headlines.return_value = []
        agent._sentiment_agent = MagicMock()

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        db.set_blackout_until(past)
        assert db.is_blackout_active() is False

        result = agent.run()
        assert result.is_blackout is False

    def test_new_trigger_resets_timer(self):
        from agents.news_agent import NewsAgent

        config = _make_config(
            rss_feed_urls="https://example.com/rss",
            blackout_keywords="fed",
            blackout_duration_hours=1.0,
        )
        db = Database(config)
        mock_mm = MagicMock()

        near_future = datetime.now(timezone.utc) + timedelta(minutes=30)
        db.set_blackout_until(near_future)

        agent = NewsAgent(config, db, mock_mm)
        agent._collector = MagicMock()
        agent._collector.fetch_headlines.return_value = [
            _make_item("Fed announces new policy"),
        ]
        agent._sentiment_agent = MagicMock()
        agent._sentiment_agent.classify.return_value = [
            SentimentResult(
                classification="Bearish",
                confidence=0.9,
                positive_score=0.05,
                negative_score=0.9,
                neutral_score=0.05,
            ),
        ]

        agent.run()
        assert db.is_blackout_active() is True
