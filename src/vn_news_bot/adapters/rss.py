from __future__ import annotations

import re
from datetime import UTC, datetime
from time import mktime
from typing import Any

import feedparser
import httpx
from loguru import logger

from vn_news_bot.domain.models import NewsArticle


def _parse_published(entry: Any) -> datetime:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime.fromtimestamp(mktime(entry.published_parsed), tz=UTC)
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        return datetime.fromtimestamp(mktime(entry.updated_parsed), tz=UTC)
    return datetime.now(tz=UTC)


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", clean).strip()


def _parse_summary(entry: Any) -> str:
    if hasattr(entry, "summary"):
        return _strip_html(str(entry.summary))[:200]
    return ""


async def fetch_rss_feed(url: str, source_name: str) -> list[NewsArticle]:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError:
        logger.warning("Failed to fetch RSS feed: %s", url)
        return []

    feed = feedparser.parse(response.text)
    articles: list[NewsArticle] = []

    for entry in feed.entries:
        title = getattr(entry, "title", "")
        link = getattr(entry, "link", "")
        if not title or not link:
            continue

        articles.append(
            NewsArticle(
                title=title,
                url=link,
                source=source_name,
                published=_parse_published(entry),
                summary=_parse_summary(entry),
                category=getattr(entry, "category", ""),
            )
        )

    return articles
