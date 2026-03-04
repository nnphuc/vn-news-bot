from __future__ import annotations

from datetime import UTC, datetime

import httpx
from loguru import logger

from vn_news_bot.config import get_newsapi_base_url
from vn_news_bot.domain.models import NewsArticle


async def fetch_top_headlines(api_key: str, country: str = "vn") -> list[NewsArticle]:
    if not api_key:
        return []

    base_url = get_newsapi_base_url()
    params: dict[str, str | int] = {
        "country": country,
        "pageSize": 10,
        "apiKey": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{base_url}/top-headlines", params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError:
        logger.warning("Failed to fetch from NewsAPI")
        return []

    articles: list[NewsArticle] = []
    for item in data.get("articles", []):
        title = item.get("title", "")
        url = item.get("url", "")
        if not title or not url:
            continue

        published_str = item.get("publishedAt", "")
        try:
            published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            published = datetime.now(tz=UTC)

        articles.append(
            NewsArticle(
                title=title,
                url=url,
                source=item.get("source", {}).get("name", "NewsAPI"),
                published=published,
                summary=item.get("description", "")[:200] if item.get("description") else "",
            )
        )

    return articles
