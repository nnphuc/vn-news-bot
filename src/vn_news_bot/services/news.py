from __future__ import annotations

import asyncio

from loguru import logger

from vn_news_bot.adapters.newsapi import fetch_top_headlines
from vn_news_bot.adapters.rss import fetch_rss_feed
from vn_news_bot.config import get_max_news_items, get_rss_feeds
from vn_news_bot.domain.models import NewsArticle, ScoredArticle
from vn_news_bot.services.scoring import score_articles


def _deduplicate(articles: list[NewsArticle]) -> list[NewsArticle]:
    seen_urls: set[str] = set()
    unique: list[NewsArticle] = []
    for article in articles:
        if article.url not in seen_urls:
            seen_urls.add(article.url)
            unique.append(article)
    return unique


async def get_latest_news(
    newsapi_key: str = "", max_items: int | None = None
) -> list[ScoredArticle]:
    rss_feeds = get_rss_feeds()
    tasks = [fetch_rss_feed(url, name) for name, url in rss_feeds.items()]

    if newsapi_key:
        tasks.append(fetch_top_headlines(newsapi_key))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_articles: list[NewsArticle] = []
    for result in results:
        if isinstance(result, list):
            all_articles.extend(result)
        elif isinstance(result, Exception):
            logger.warning("Feed fetch failed: %s", result)

    all_articles = _deduplicate(all_articles)

    limit = max_items if max_items is not None else get_max_news_items()
    return score_articles(all_articles, max_items=limit)
