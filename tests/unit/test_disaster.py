from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from vn_news_bot.domain.models import (
    AlertSeverity,
    ArticleClassification,
    NewsArticle,
)
from vn_news_bot.services.disaster import (
    _keyword_fallback,
    _strip_exclude_phrases,
    classify_and_filter_disasters,
)


def _make_article(title: str, summary: str = "") -> NewsArticle:
    return NewsArticle(
        title=title,
        url=f"https://example.com/{hash(title)}",
        source="VnExpress",
        published=datetime(2026, 3, 31, 10, 0, tzinfo=UTC),
        summary=summary,
    )


class TestStripExcludePhrases:
    def test_strips_bao_gia(self) -> None:
        result = _strip_exclude_phrases("Doanh nghiệp vượt bão giá xăng dầu")
        assert "bão giá" not in result.lower()

    def test_strips_bao_xang_dau(self) -> None:
        result = _strip_exclude_phrases("Ứng phó với bão xăng dầu tăng vọt")
        assert "bão xăng dầu" not in result.lower()

    def test_preserves_real_bao(self) -> None:
        result = _strip_exclude_phrases("Bão số 5 đổ bộ miền Trung")
        assert "bão" in result.lower()

    def test_mixed_context(self) -> None:
        text = "Bão giá xăng dầu giữa mùa bão lũ miền Trung"
        result = _strip_exclude_phrases(text)
        assert "bão giá" not in result.lower()
        assert "bão lũ" in result.lower()


class TestKeywordFallback:
    def test_real_disaster(self) -> None:
        result = _keyword_fallback("Bão số 5 đổ bộ miền Trung", "Gây thiệt hại lớn")
        assert result.is_disaster is True
        assert result.disaster_severity in ("high", "medium", "low")

    def test_metaphorical_storm(self) -> None:
        result = _keyword_fallback("Doanh nghiệp vượt bão giá", "Kinh tế khó khăn")
        assert result.is_disaster is False

    def test_no_keywords(self) -> None:
        result = _keyword_fallback("Kinh tế Việt Nam tăng trưởng", "GDP tăng 6%")
        assert result.is_disaster is False

    def test_weather_keywords(self) -> None:
        result = _keyword_fallback("Nắng nóng gay gắt", "Nhiệt độ 37 độ C")
        assert result.is_disaster is True
        assert result.disaster_severity == "low"


class TestClassifyAndFilterDisasters:
    def test_llm_classifies_disaster(self) -> None:
        articles = [_make_article("Bão số 5 đổ bộ miền Trung")]
        mock_classifier = MagicMock()
        mock_classifier.classify_article.return_value = ArticleClassification(
            disaster_severity="high", is_hot=True
        )

        alerts, classifications = classify_and_filter_disasters(articles, mock_classifier)

        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.HIGH
        assert classifications[0].is_hot is True

    def test_llm_filters_false_positive(self) -> None:
        articles = [_make_article("Doanh nghiệp vượt bão giá xăng dầu")]
        mock_classifier = MagicMock()
        mock_classifier.classify_article.return_value = ArticleClassification(
            disaster_severity="none", is_hot=False
        )

        alerts, _ = classify_and_filter_disasters(articles, mock_classifier)

        assert len(alerts) == 0

    def test_no_classifier_uses_fallback(self) -> None:
        articles = [_make_article("Bão số 5 đổ bộ", "Bão gây lũ lụt")]

        alerts, _ = classify_and_filter_disasters(articles, classifier=None)

        assert len(alerts) >= 1

    def test_multiple_articles_sorted_by_severity(self) -> None:
        articles = [
            _make_article("Nắng nóng gay gắt"),
            _make_article("Bão số 5 đổ bộ miền Trung"),
        ]
        mock_classifier = MagicMock()
        mock_classifier.classify_article.side_effect = [
            ArticleClassification(disaster_severity="low", is_hot=False),
            ArticleClassification(disaster_severity="high", is_hot=True),
        ]

        alerts, _ = classify_and_filter_disasters(articles, mock_classifier)

        assert len(alerts) == 2
        assert alerts[0].severity == AlertSeverity.HIGH
        assert alerts[1].severity == AlertSeverity.LOW

    def test_respects_max_items(self) -> None:
        articles = [_make_article(f"Bão số {i}") for i in range(10)]
        mock_classifier = MagicMock()
        mock_classifier.classify_article.return_value = ArticleClassification(
            disaster_severity="high"
        )

        alerts, _ = classify_and_filter_disasters(articles, mock_classifier)

        assert len(alerts) <= 5  # max_disaster_items from config
