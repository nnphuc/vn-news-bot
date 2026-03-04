from __future__ import annotations

from datetime import UTC, datetime

from vn_news_bot.domain.models import NewsArticle
from vn_news_bot.services.news import _deduplicate


def test_deduplicate_removes_duplicates() -> None:
    articles = [
        NewsArticle(
            title="Article 1",
            url="https://example.com/1",
            source="A",
            published=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        NewsArticle(
            title="Article 1 copy",
            url="https://example.com/1",
            source="B",
            published=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        NewsArticle(
            title="Article 2",
            url="https://example.com/2",
            source="A",
            published=datetime(2026, 1, 1, tzinfo=UTC),
        ),
    ]
    result = _deduplicate(articles)
    assert len(result) == 2
    assert result[0].url == "https://example.com/1"
    assert result[1].url == "https://example.com/2"


def test_deduplicate_empty_list() -> None:
    assert _deduplicate([]) == []


def test_deduplicate_no_duplicates() -> None:
    articles = [
        NewsArticle(
            title=f"Article {i}",
            url=f"https://example.com/{i}",
            source="A",
            published=datetime(2026, 1, 1, tzinfo=UTC),
        )
        for i in range(3)
    ]
    result = _deduplicate(articles)
    assert len(result) == 3
