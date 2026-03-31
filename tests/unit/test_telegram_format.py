from __future__ import annotations

from datetime import UTC, datetime

from vn_news_bot.adapters.telegram import format_disaster_message, format_hot_news_digest
from vn_news_bot.domain.models import AlertSeverity, DisasterAlert, NewsArticle, ScoredArticle


def _make_alert(
    title: str = "Bão số 5",
    severity: AlertSeverity = AlertSeverity.HIGH,
) -> DisasterAlert:
    return DisasterAlert(
        title=title,
        description="Mô tả ngắn về thiên tai",
        severity=severity,
        source="VnExpress",
        url="https://vnexpress.net/bao-5",
        published=datetime(2026, 3, 31, 14, 30, tzinfo=UTC),
    )


def _make_scored(
    title: str = "Breaking news",
    source: str = "VnExpress",
) -> ScoredArticle:
    article = NewsArticle(
        title=title,
        url="https://example.com/hot",
        source=source,
        published=datetime(2026, 3, 31, 10, 30, tzinfo=UTC),
        summary="Short description of article",
    )
    return ScoredArticle(article=article, score=0.9, category="Thời sự", category_emoji="📌")


class TestFormatDisasterMessage:
    def test_empty_alerts(self) -> None:
        result = format_disaster_message([])
        assert "Không có" in result

    def test_html_structure(self) -> None:
        alert = _make_alert()
        result = format_disaster_message([alert])
        assert "<b>CẢNH BÁO THIÊN TAI</b>" in result
        assert "🔴" in result
        assert '<a href="https://vnexpress.net/bao-5">' in result
        assert "<blockquote>" in result
        assert "<i>VnExpress" in result

    def test_severity_emojis(self) -> None:
        for severity, emoji in [
            (AlertSeverity.HIGH, "🔴"),
            (AlertSeverity.MEDIUM, "🟠"),
            (AlertSeverity.LOW, "🟡"),
        ]:
            result = format_disaster_message([_make_alert(severity=severity)])
            assert emoji in result

    def test_no_severity_text_label(self) -> None:
        result = format_disaster_message([_make_alert()])
        assert "[HIGH]" not in result
        assert "[MEDIUM]" not in result

    def test_escapes_html(self) -> None:
        alert = _make_alert(title="Test <script> & alert")
        result = format_disaster_message([alert])
        assert "&lt;script&gt;" in result
        assert "&amp;" in result


class TestFormatHotNewsDigest:
    def test_with_hot_and_regular(self) -> None:
        hot = [_make_scored("Tin nóng nhất")]
        regular = [_make_scored("Tin thường")]
        result = format_hot_news_digest(hot, regular)
        assert "<b>TIN NÓNG</b>" in result
        assert "📌" in result
        assert "<b>TIN TỨC</b>" in result

    def test_no_hot_articles(self) -> None:
        regular = [_make_scored("Tin thường")]
        result = format_hot_news_digest([], regular)
        assert "TIN NÓNG" not in result
        assert "<b>TIN TỨC</b>" in result

    def test_hot_has_blockquote(self) -> None:
        hot = [_make_scored("Tin nóng")]
        result = format_hot_news_digest(hot, [])
        assert "<blockquote>" in result

    def test_empty_all(self) -> None:
        result = format_hot_news_digest([], [])
        assert "Không có tin tức mới" in result
