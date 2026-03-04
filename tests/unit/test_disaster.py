from __future__ import annotations

from datetime import UTC, datetime

from vn_news_bot.adapters.telegram import format_disaster_message
from vn_news_bot.domain.models import AlertSeverity, DisasterAlert, NewsArticle
from vn_news_bot.services.disaster import _article_to_alert, _determine_severity, _match_keywords


def test_match_keywords_found() -> None:
    result = _match_keywords("Bão số 5 gây mưa lớn", ["bão", "mưa lớn", "lũ"])
    assert "bão" in result
    assert "mưa lớn" in result
    assert "lũ" not in result


def test_match_keywords_none() -> None:
    result = _match_keywords("Thời tiết đẹp hôm nay", ["bão", "lũ"])
    assert result == []


def test_match_keywords_case_insensitive() -> None:
    result = _match_keywords("STORM warning", ["storm"])
    assert "storm" in result


def test_determine_severity_critical() -> None:
    matched = ["bão", "động đất"]
    severity = _determine_severity(matched)
    assert severity == AlertSeverity.CRITICAL


def test_determine_severity_high() -> None:
    matched = ["bão"]
    severity = _determine_severity(matched)
    assert severity == AlertSeverity.HIGH


def test_determine_severity_medium() -> None:
    matched = ["mưa lớn", "giông"]
    severity = _determine_severity(matched)
    assert severity == AlertSeverity.MEDIUM


def test_determine_severity_low() -> None:
    matched = ["nắng nóng"]
    severity = _determine_severity(matched)
    assert severity == AlertSeverity.LOW


def test_article_to_alert_match(sample_disaster_article: NewsArticle) -> None:
    alert = _article_to_alert(sample_disaster_article)
    assert alert is not None
    assert "bão" in alert.keywords_matched
    assert alert.severity in (AlertSeverity.HIGH, AlertSeverity.CRITICAL)


def test_article_to_alert_no_match() -> None:
    article = NewsArticle(
        title="Kinh tế Việt Nam tăng trưởng",
        url="https://example.com/kt",
        source="VnExpress",
        published=datetime(2026, 1, 1, tzinfo=UTC),
        summary="GDP tăng 6%",
    )
    assert _article_to_alert(article) is None


def test_format_disaster_message_empty() -> None:
    assert "Không có" in format_disaster_message([])


def test_format_disaster_message(sample_alert: DisasterAlert) -> None:
    text = format_disaster_message([sample_alert])
    assert "Cảnh báo thiên tai" in text
    assert "Bão số 5" in text
