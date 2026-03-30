from __future__ import annotations

from datetime import datetime, timezone, timedelta

from core.config import AppConfig
from core.logger import get_logger
from core.types import MacroSentiment, NewsItem, SentimentResult
from data.news_data import NewsCollector
from models.model_manager import ModelManager
from storage.database import Database

from agents.sentiment_agent import SentimentAgent

logger = get_logger(__name__)

_DIRECTION_SIGN = {"Bullish": 1.0, "Bearish": -1.0, "Neutral": 0.0}


class NewsAgent:
    def __init__(
        self, config: AppConfig, database: Database, model_manager: ModelManager
    ):
        self._config = config
        self._db = database
        self._collector = NewsCollector(
            feed_urls=[u.strip() for u in config.rss_feed_urls.split(",") if u.strip()],
            keywords=[
                kw.strip() for kw in config.rss_keywords.split(",") if kw.strip()
            ],
        )
        self._sentiment_agent = SentimentAgent(config, model_manager)
        self._blackout_keywords = [
            kw.strip().lower()
            for kw in config.blackout_keywords.split(",")
            if kw.strip()
        ]

    def run(self) -> MacroSentiment:
        self._db.clear_expired_blackout()

        news_items = self._collector.fetch_headlines()
        if not news_items:
            return MacroSentiment(
                macro_score=0.0,
                headline_count=0,
                is_blackout=self._db.is_blackout_active(),
            )

        sentiments = self._sentiment_agent.classify(news_items)
        self._persist_results(news_items, sentiments)
        self._check_blackout_keywords(news_items)
        macro_score = self._compute_macro_score()
        headline_count = len(sentiments)

        return MacroSentiment(
            macro_score=macro_score,
            headline_count=headline_count,
            sentiments=sentiments,
            is_blackout=self._db.is_blackout_active(),
        )

    def _check_blackout_keywords(self, items: list[NewsItem]) -> None:
        for item in items:
            lower = item.headline.lower()
            if any(kw in lower for kw in self._blackout_keywords):
                until = datetime.now(timezone.utc) + timedelta(
                    hours=self._config.blackout_duration_hours
                )
                self._db.set_blackout_until(until)
                logger.info(
                    "Blackout triggered by headline: '%s' (until %s)",
                    item.headline,
                    until.isoformat(),
                )
                return

    def _persist_results(
        self, items: list[NewsItem], results: list[SentimentResult]
    ) -> None:
        for item, result in zip(items, results):
            content_hash = NewsCollector._content_hash(item.headline)
            if not self._db.check_hash_exists(content_hash):
                self._db.save_news(
                    item, result.classification, result.confidence, content_hash
                )

    def _compute_macro_score(self) -> float:
        rows = self._db.get_recent_news(self._config.sentiment_window_hours)
        if not rows:
            return 0.0
        total = 0.0
        for row in rows:
            direction = _DIRECTION_SIGN.get(row.get("classification", "Neutral"), 0.0)
            confidence = row.get("confidence", 0.0) or 0.0
            total += direction * confidence
        return total / len(rows)
