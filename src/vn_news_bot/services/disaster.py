from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

from vn_news_bot.adapters.rss import fetch_rss_feed
from vn_news_bot.config import (
    get_critical_keywords,
    get_disaster_keywords,
    get_exclude_phrases,
    get_max_disaster_items,
    get_rss_feeds,
)
from vn_news_bot.domain.models import (
    AlertSeverity,
    ArticleClassification,
    DisasterAlert,
    NewsArticle,
)

if TYPE_CHECKING:
    from vn_news_bot.adapters.llm import LLMClassifier


def _strip_exclude_phrases(text: str) -> str:
    result = text
    for phrase in get_exclude_phrases():
        lower = result.lower()
        phrase_lower = phrase.lower()
        while phrase_lower in lower:
            idx = lower.index(phrase_lower)
            result = result[:idx] + result[idx + len(phrase):]
            lower = result.lower()
    return result


def _match_keywords(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def _determine_severity(matched: list[str]) -> str:
    critical_lower = {k.lower() for k in get_critical_keywords()}
    critical_matches = [kw for kw in matched if kw.lower() in critical_lower]
    if critical_matches:
        return "high"
    return "medium" if len(matched) > 1 else "low"


def _keyword_fallback(title: str, summary: str) -> ArticleClassification:
    search_text = _strip_exclude_phrases(f"{title} {summary}")
    matched = _match_keywords(search_text, get_disaster_keywords())
    if not matched:
        return ArticleClassification()
    severity = _determine_severity(matched)
    return ArticleClassification(disaster_severity=severity, is_hot=False)


def classify_and_filter_disasters(
    articles: list[NewsArticle],
    classifier: LLMClassifier | None,
) -> tuple[list[DisasterAlert], list[ArticleClassification]]:
    classifications: list[ArticleClassification] = []
    alerts: list[DisasterAlert] = []

    for article in articles:
        if classifier is not None:
            try:
                classification = classifier.classify_article(article.title)
            except Exception:
                logger.warning("LLM failed, using fallback for: {}", article.title)
                classification = _keyword_fallback(article.title, article.summary)
        else:
            classification = _keyword_fallback(article.title, article.summary)

        classifications.append(classification)

        if classification.is_disaster:
            severity = classification.to_alert_severity()
            if severity is not None:
                alerts.append(
                    DisasterAlert(
                        title=article.title,
                        description=article.summary,
                        severity=severity,
                        source=article.source,
                        url=article.url,
                        published=article.published,
                    )
                )

    severity_rank = {
        AlertSeverity.LOW: 1,
        AlertSeverity.MEDIUM: 2,
        AlertSeverity.HIGH: 3,
        AlertSeverity.CRITICAL: 4,
    }
    alerts.sort(key=lambda a: (severity_rank.get(a.severity, 0), a.published), reverse=True)
    return alerts[: get_max_disaster_items()], classifications


async def get_disaster_alerts(
    classifier: LLMClassifier | None = None,
) -> tuple[list[DisasterAlert], list[ArticleClassification]]:
    rss_feeds = get_rss_feeds()
    tasks = [fetch_rss_feed(url, name) for name, url in rss_feeds.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_articles: list[NewsArticle] = []
    for result in results:
        if isinstance(result, list):
            all_articles.extend(result)
        elif isinstance(result, Exception):
            logger.warning("Feed fetch failed: {}", result)

    return classify_and_filter_disasters(all_articles, classifier)
