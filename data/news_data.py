from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from time import struct_time

import feedparser
import requests

from core.logger import get_logger
from core.types import NewsItem

logger = get_logger(__name__)


def _parse_published(entry) -> datetime:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed and isinstance(parsed, struct_time):
            from datetime import timedelta
            import calendar

            ts = calendar.timegm(parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    return datetime.now(timezone.utc)


class NewsCollector:
    def __init__(self, feed_urls: list[str], keywords: list[str]):
        self._feed_urls = feed_urls
        self._keywords = [kw.lower().strip() for kw in keywords if kw.strip()]

    def fetch_headlines(self) -> list[NewsItem]:
        all_items = []
        for url in self._feed_urls:
            items = self._fetch_feed(url)
            all_items.extend(items)
        return self._deduplicate(all_items)

    def _fetch_feed(self, url: str) -> list[NewsItem]:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            feed = feedparser.parse(response.text)
        except Exception as e:
            logger.warning("Failed to fetch RSS feed %s: %s", url, e)
            return []

        items = []
        for entry in feed.entries:
            title = getattr(entry, "title", "").strip()
            if not title:
                continue
            if not self._matches_keywords(title):
                continue
            link = getattr(entry, "link", "")
            published_at = _parse_published(entry)
            source = url.split("/")[2] if "/" in url else url
            items.append(
                NewsItem(
                    source=source,
                    headline=title,
                    url=link,
                    published_at=published_at,
                )
            )
        logger.info("Fetched %d matching headlines from %s", len(items), url)
        return items

    def _matches_keywords(self, text: str) -> bool:
        if not self._keywords:
            return True
        lower = text.lower()
        return any(kw in lower for kw in self._keywords)

    def _deduplicate(self, items: list[NewsItem]) -> list[NewsItem]:
        seen = set()
        unique = []
        for item in items:
            h = self._content_hash(item.headline)
            if h not in seen:
                seen.add(h)
                unique.append(item)
        return unique

    @staticmethod
    def _content_hash(headline: str) -> str:
        normalized = headline.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()
