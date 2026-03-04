from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vn_news_bot.domain.models import AlertSeverity, DisasterAlert, NewsArticle, WeatherReport


def test_news_article_display_text() -> None:
    article = NewsArticle(
        title="Test headline",
        url="https://example.com/test",
        source="VnExpress",
        published=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert "[VnExpress]" in article.display_text
    assert "Test headline" in article.display_text
    assert "https://example.com/test" in article.display_text


def test_news_article_display_text_no_source() -> None:
    article = NewsArticle(
        title="Test",
        url="https://example.com",
        source="",
        published=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert "[]" not in article.display_text


def test_weather_report_display_text() -> None:
    report = WeatherReport(
        city="Hanoi",
        temperature=30.0,
        feels_like=34.0,
        humidity=80,
        description="nắng",
        wind_speed=2.5,
    )
    text = report.display_text
    assert "Hanoi" in text
    assert "30°C" in text
    assert "34°C" in text
    assert "80%" in text
    assert "2.5 m/s" in text


def test_disaster_alert_severity_emoji() -> None:
    alert = DisasterAlert(
        title="Test",
        description="",
        severity=AlertSeverity.CRITICAL,
        source="test",
        url="https://example.com",
        published=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert alert.severity_emoji == "🚨"


def test_disaster_alert_display_text() -> None:
    alert = DisasterAlert(
        title="Bão số 5",
        description="Bão mạnh",
        severity=AlertSeverity.HIGH,
        source="VnExpress",
        url="https://example.com/bao",
        published=datetime(2026, 1, 1, tzinfo=UTC),
        keywords_matched=["bão"],
    )
    text = alert.display_text
    assert "🔴" in text
    assert "HIGH" in text
    assert "Bão số 5" in text


def test_news_article_is_frozen() -> None:
    article = NewsArticle(
        title="Test",
        url="https://example.com",
        source="test",
        published=datetime(2026, 1, 1, tzinfo=UTC),
    )
    with pytest.raises(AttributeError):
        article.title = "Modified"  # type: ignore[misc]
