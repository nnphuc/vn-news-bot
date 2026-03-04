from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vn_news_bot.domain.models import AlertSeverity, DisasterAlert, NewsArticle, WeatherReport


@pytest.fixture
def sample_articles() -> list[NewsArticle]:
    return [
        NewsArticle(
            title="Tin tức thứ nhất",
            url="https://example.com/1",
            source="VnExpress",
            published=datetime(2026, 3, 4, 10, 0, tzinfo=UTC),
            summary="Tóm tắt tin 1",
        ),
        NewsArticle(
            title="Tin tức thứ hai",
            url="https://example.com/2",
            source="Tuổi Trẻ",
            published=datetime(2026, 3, 4, 9, 0, tzinfo=UTC),
            summary="Tóm tắt tin 2",
        ),
        NewsArticle(
            title="Tin tức thứ ba",
            url="https://example.com/3",
            source="Thanh Niên",
            published=datetime(2026, 3, 4, 8, 0, tzinfo=UTC),
            summary="Tóm tắt tin 3",
        ),
    ]


@pytest.fixture
def sample_weather() -> WeatherReport:
    return WeatherReport(
        city="Hanoi",
        temperature=28.5,
        feels_like=32.0,
        humidity=75,
        description="mây rải rác",
        wind_speed=3.5,
    )


@pytest.fixture
def sample_disaster_article() -> NewsArticle:
    return NewsArticle(
        title="Bão số 5 đổ bộ miền Trung",
        url="https://example.com/bao",
        source="VnExpress",
        published=datetime(2026, 3, 4, 6, 0, tzinfo=UTC),
        summary="Bão số 5 gây mưa lớn và lũ lụt tại các tỉnh miền Trung",
    )


@pytest.fixture
def sample_alert() -> DisasterAlert:
    return DisasterAlert(
        title="Bão số 5 đổ bộ miền Trung",
        description="Bão số 5 gây mưa lớn",
        severity=AlertSeverity.HIGH,
        source="VnExpress",
        url="https://example.com/bao",
        published=datetime(2026, 3, 4, 6, 0, tzinfo=UTC),
        keywords_matched=["bão", "mưa lớn", "lũ lụt"],
    )
