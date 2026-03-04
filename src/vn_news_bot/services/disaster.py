from __future__ import annotations

import asyncio

from loguru import logger

from vn_news_bot.adapters.rss import fetch_rss_feed
from vn_news_bot.config import (
    get_critical_keywords,
    get_disaster_keywords,
    get_max_disaster_items,
    get_rss_feeds,
)
from vn_news_bot.domain.models import AlertSeverity, DisasterAlert, NewsArticle


def _match_keywords(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def _determine_severity(matched: list[str]) -> AlertSeverity:
    critical_lower = {k.lower() for k in get_critical_keywords()}
    critical_matches = [kw for kw in matched if kw.lower() in critical_lower]
    if critical_matches:
        return AlertSeverity.CRITICAL if len(critical_matches) > 1 else AlertSeverity.HIGH
    return AlertSeverity.MEDIUM if len(matched) > 1 else AlertSeverity.LOW


def _article_to_alert(article: NewsArticle) -> DisasterAlert | None:
    search_text = f"{article.title} {article.summary}"
    matched = _match_keywords(search_text, get_disaster_keywords())
    if not matched:
        return None

    return DisasterAlert(
        title=article.title,
        description=article.summary,
        severity=_determine_severity(matched),
        source=article.source,
        url=article.url,
        published=article.published,
        keywords_matched=matched,
    )


async def get_disaster_alerts() -> list[DisasterAlert]:
    rss_feeds = get_rss_feeds()
    tasks = [fetch_rss_feed(url, name) for name, url in rss_feeds.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_articles: list[NewsArticle] = []
    for result in results:
        if isinstance(result, list):
            all_articles.extend(result)
        elif isinstance(result, Exception):
            logger.warning("Feed fetch failed: %s", result)

    alerts: list[DisasterAlert] = []
    for article in all_articles:
        alert = _article_to_alert(article)
        if alert:
            alerts.append(alert)

    alerts.sort(key=lambda a: (a.severity.value, a.published), reverse=True)
    return alerts[: get_max_disaster_items()]
