from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from vn_news_bot.domain.models import NewsArticle, ScoreBreakdown, ScoredArticle
from vn_news_bot.services.scoring import (
    _classify_article,
    _classify_with_fallback,
    _classify_with_nlp,
    _find_clusters,
    _jaccard_similarity,
    _normalize_title,
    _tokenize,
    _tokenize_vi,
    score_articles,
)
from vn_news_bot.utils.text import strip_accents


def _make_article(
    title: str = "Test article",
    source: str = "VnExpress",
    hours_ago: float = 1.0,
    url: str | None = None,
    category: str = "",
) -> NewsArticle:
    now = datetime.now(UTC)
    return NewsArticle(
        title=title,
        url=url or f"https://example.com/{title.replace(' ', '-')}",
        source=source,
        published=now - timedelta(hours=hours_ago),
        category=category,
    )


class TestNormalizeTitle:
    def test_lowercase_and_strip(self) -> None:
        assert _normalize_title("  Hello WORLD  ") == "hello world"

    def test_removes_punctuation(self) -> None:
        result = _normalize_title("Tin tức: Việt Nam - Mỹ!")
        assert ":" not in result
        assert "!" not in result
        assert "-" not in result

    def test_collapses_whitespace(self) -> None:
        assert _normalize_title("a   b  c") == "a b c"

    def test_unicode_normalization(self) -> None:
        result = _normalize_title("Việt Nam")
        assert result == "việt nam"


class TestTokenize:
    def test_basic_tokenization(self) -> None:
        tokens = _tokenize("thủ tướng gặp tổng thống", set())
        assert "thủ" in tokens
        assert "tướng" in tokens
        assert "thủ tướng" in tokens
        assert "gặp tổng" in tokens

    def test_filters_stopwords(self) -> None:
        tokens = _tokenize("thủ tướng và tổng thống", {"và"})
        assert "và" not in tokens
        assert "thủ tướng" in tokens

    def test_filters_short_tokens(self) -> None:
        tokens = _tokenize("a b thử", set())
        assert "a" not in tokens
        assert "b" not in tokens
        assert "thử" in tokens

    def test_empty_input(self) -> None:
        assert _tokenize("", set()) == set()


class TestJaccardSimilarity:
    def test_identical_sets(self) -> None:
        s = {"a", "b", "c"}
        assert _jaccard_similarity(s, s) == 1.0

    def test_disjoint_sets(self) -> None:
        assert _jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self) -> None:
        sim = _jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        assert abs(sim - 0.5) < 0.01

    def test_empty_set(self) -> None:
        assert _jaccard_similarity(set(), {"a"}) == 0.0
        assert _jaccard_similarity(set(), set()) == 0.0


class TestFindClusters:
    def test_similar_titles_cluster(self) -> None:
        articles = [
            _make_article("Thủ tướng gặp Tổng thống Mỹ tại Hà Nội", "VnExpress"),
            _make_article("Thủ tướng gặp gỡ Tổng thống Mỹ tại Hà Nội", "Tuổi Trẻ"),
        ]
        clusters = _find_clusters(articles, set(), 0.4)
        assert len(clusters) == 1
        assert sorted(clusters[0]) == [0, 1]

    def test_different_titles_no_cluster(self) -> None:
        articles = [
            _make_article("Thủ tướng gặp Tổng thống Mỹ", "VnExpress"),
            _make_article("VN-Index tăng mạnh phiên cuối tuần", "VnEconomy"),
        ]
        clusters = _find_clusters(articles, set(), 0.4)
        assert len(clusters) == 0

    def test_three_articles_one_cluster(self) -> None:
        articles = [
            _make_article("Bão số 5 đổ bộ miền Trung gây thiệt hại", "VnExpress"),
            _make_article("Bão số 5 đổ bộ vào miền Trung Việt Nam", "Tuổi Trẻ"),
            _make_article("Bão số 5 gây thiệt hại nặng miền Trung", "Thanh Niên"),
        ]
        clusters = _find_clusters(articles, set(), 0.4)
        assert len(clusters) == 1
        assert len(clusters[0]) == 3


class TestStripAccents:
    def test_removes_vietnamese_accents(self) -> None:
        assert strip_accents("Việt Nam") == "viet nam"

    def test_handles_d_stroke(self) -> None:
        assert strip_accents("Đà Nẵng") == "da nang"

    def test_already_unaccented(self) -> None:
        assert strip_accents("hello world") == "hello world"


class TestTokenizeVi:
    def test_segments_compound_words(self) -> None:
        tokens = _tokenize_vi("Thủ tướng họp bàn chính sách")
        assert "thủ tướng" in tokens
        assert "chính sách" in tokens

    def test_lowercase_output(self) -> None:
        tokens = _tokenize_vi("GDP Tăng Trưởng")
        assert all(t == t.lower() for t in tokens)

    def test_empty_input(self) -> None:
        assert _tokenize_vi("") == [] or _tokenize_vi("") == [""]
        # word_tokenize may return empty list or single empty string

    def test_fallback_on_simple_text(self) -> None:
        tokens = _tokenize_vi("hello world test")
        assert "hello" in tokens
        assert "world" in tokens


class TestClassifyWithNlp:
    @patch("vn_news_bot.services.scoring.classify")
    def test_maps_nlp_category(self, mock_classify: object) -> None:
        from unittest.mock import MagicMock

        mock = MagicMock(return_value="The thao")
        with patch("vn_news_bot.services.scoring.classify", mock):
            result = _classify_with_nlp("Đội tuyển bóng rổ tranh tài")
            assert result is not None
            assert result[0] == "Thể thao"

    @patch("vn_news_bot.services.scoring.classify")
    def test_returns_none_for_unmapped(self, mock_classify: object) -> None:
        from unittest.mock import MagicMock

        mock = MagicMock(return_value="Unknown Category")
        with patch("vn_news_bot.services.scoring.classify", mock):
            result = _classify_with_nlp("Some random title")
            assert result is None

    @patch("vn_news_bot.services.scoring.classify")
    def test_handles_classify_exception(self, mock_classify: object) -> None:
        from unittest.mock import MagicMock

        mock = MagicMock(side_effect=RuntimeError("model error"))
        with patch("vn_news_bot.services.scoring.classify", mock):
            result = _classify_with_nlp("Any title")
            assert result is None


class TestClassifyArticle:
    def test_politics(self) -> None:
        name, emoji, _boost = _classify_article("Thủ tướng họp bàn chính sách mới")
        assert name == "Thời sự"
        assert emoji == "📌"

    def test_economy(self) -> None:
        name, emoji, _boost = _classify_article("Ngân hàng tăng lãi suất huy động")
        assert name == "Kinh tế"
        assert emoji == "💰"

    def test_sports(self) -> None:
        name, emoji, _boost = _classify_article("U23 Việt Nam thắng Thái Lan bóng đá")
        assert name == "Thể thao"
        assert emoji == "⚽"

    def test_unknown(self) -> None:
        name, emoji, boost = _classify_article("Something completely random xyz")
        assert name == "Khác"
        assert emoji == "📋"
        assert boost == 0.0

    def test_multi_keyword_wins(self) -> None:
        """Article matching more keywords in one category should pick that category."""
        name, _emoji, _boost = _classify_article("Ngân hàng tăng lãi suất, tỷ giá biến động mạnh")
        assert name == "Kinh tế"

    def test_accent_insensitive(self) -> None:
        """Should classify even when title has no Vietnamese accents."""
        name, _emoji, _boost = _classify_article("Thu tuong hop ban chinh sach moi")
        assert name == "Thời sự"


class TestClassifyWithFallback:
    @patch("vn_news_bot.services.scoring._classify_with_nlp", return_value=None)
    def test_rss_category_map_fallback(self, _mock_nlp: object) -> None:
        article = _make_article("Tin tức ngắn gọn", category="the-thao")
        name, emoji, _boost = _classify_with_fallback(article)
        assert name == "Thể thao"
        assert emoji == "⚽"

    @patch("vn_news_bot.services.scoring._classify_with_nlp", return_value=None)
    def test_rss_category_map_vietnamese(self, _mock_nlp: object) -> None:
        article = _make_article("Tin mới nhất", category="kinh doanh")
        name, _emoji, _boost = _classify_with_fallback(article)
        assert name == "Kinh tế"

    def test_title_classification_takes_priority(self) -> None:
        article = _make_article("Ngân hàng tăng lãi suất mạnh", category="the-thao")
        name, _emoji, _boost = _classify_with_fallback(article)
        assert name == "Kinh tế"

    @patch("vn_news_bot.services.scoring.classify")
    def test_nlp_fallback_before_rss(self, mock_classify: object) -> None:
        from unittest.mock import MagicMock

        mock = MagicMock(return_value="The thao")
        with patch("vn_news_bot.services.scoring.classify", mock):
            article = _make_article("Tin tức ngắn gọn không keyword", category="kinh doanh")
            name, _emoji, _boost = _classify_with_fallback(article)
            assert name == "Thể thao"


class TestScoreArticles:
    def test_empty_list(self) -> None:
        assert score_articles([]) == []

    def test_newer_article_scores_higher(self) -> None:
        now = datetime.now(UTC)
        articles = [
            _make_article("Tin cũ", "VnExpress", hours_ago=24),
            _make_article("Tin mới", "VnExpress", hours_ago=0.5),
        ]
        scored = score_articles(articles, now=now)
        scores = {s.article.title: s.score for s in scored}
        assert scores["Tin mới"] > scores["Tin cũ"]

    def test_trusted_source_scores_higher(self) -> None:
        now = datetime.now(UTC)
        articles = [
            _make_article("Thủ tướng ban hành chính sách kinh tế", "VnExpress", hours_ago=1),
            _make_article("Giải bóng đá vô địch quốc gia khai mạc", "24h", hours_ago=1),
        ]
        scored = score_articles(articles, now=now)
        scores = {s.article.source: s.score for s in scored}
        assert scores["VnExpress"] > scores["24h"]

    def test_trending_articles_flagged(self) -> None:
        now = datetime.now(UTC)
        articles = [
            _make_article("Thủ tướng gặp Tổng thống Mỹ tại Hà Nội", "VnExpress", hours_ago=1),
            _make_article("Thủ tướng gặp gỡ Tổng thống Mỹ tại Hà Nội", "Tuổi Trẻ", hours_ago=1),
            _make_article("VN-Index giảm mạnh hôm nay", "VnEconomy", hours_ago=1),
        ]
        scored = score_articles(articles, now=now)
        trending = [s for s in scored if s.is_trending]
        non_trending = [s for s in scored if not s.is_trending]
        assert len(trending) >= 1
        assert len(non_trending) >= 1

    def test_keyword_boost_applied(self) -> None:
        now = datetime.now(UTC)
        articles = [
            _make_article("Thủ tướng ban hành chính sách mới", "VnExpress", hours_ago=1),
            _make_article("Tin giải trí ngày hôm nay vui", "VnExpress", hours_ago=1),
        ]
        scored = score_articles(articles, now=now)
        by_title = {s.article.title: s for s in scored}
        politics = by_title["Thủ tướng ban hành chính sách mới"]
        entertainment = by_title["Tin giải trí ngày hôm nay vui"]
        assert politics.breakdown.keyword_boost > entertainment.breakdown.keyword_boost

    def test_categories_assigned(self) -> None:
        now = datetime.now(UTC)
        articles = [
            _make_article("GDP tăng trưởng xuất khẩu mạnh", "VnEconomy", hours_ago=1),
        ]
        scored = score_articles(articles, now=now)
        assert scored[0].category == "Kinh tế"
        assert scored[0].category_emoji == "💰"

    def test_scored_article_properties(self) -> None:
        breakdown = ScoreBreakdown(recency=0.9, source_trust=0.8, trending=0.5, keyword_boost=0.6)
        article = _make_article("Test", "VnExpress")
        scored = ScoredArticle(
            article=article,
            score=0.75,
            category="Thời sự",
            category_emoji="📌",
            trending_sources=["VnExpress", "Tuổi Trẻ"],
            breakdown=breakdown,
        )
        assert scored.is_trending is True

    def test_single_source_not_trending(self) -> None:
        article = _make_article("Test", "VnExpress")
        scored = ScoredArticle(
            article=article,
            score=0.5,
            trending_sources=["VnExpress"],
        )
        assert scored.is_trending is False


class TestHotNewsScoring:
    def test_hot_article_gets_split(self) -> None:
        from vn_news_bot.domain.models import ArticleClassification
        from vn_news_bot.services.scoring import split_hot_articles

        now = datetime.now(UTC)
        articles = [
            _make_article("Thủ tướng ban hành chính sách mới", hours_ago=1),
            _make_article("Tin giải trí ngày hôm nay", hours_ago=1),
        ]
        classifications = [
            ArticleClassification(disaster_severity="none", is_hot=True),
            ArticleClassification(disaster_severity="none", is_hot=False),
        ]

        scored = score_articles(articles, now=now)
        hot, regular = split_hot_articles(scored, classifications)

        assert len(hot) == 1
        assert hot[0].article.title == "Thủ tướng ban hành chính sách mới"
        assert len(regular) >= 1

    def test_no_hot_articles(self) -> None:
        from vn_news_bot.domain.models import ArticleClassification
        from vn_news_bot.services.scoring import split_hot_articles

        now = datetime.now(UTC)
        articles = [_make_article("Tin thường ngày", hours_ago=1)]
        classifications = [ArticleClassification(disaster_severity="none", is_hot=False)]

        scored = score_articles(articles, now=now)
        hot, regular = split_hot_articles(scored, classifications)

        assert len(hot) == 0
        assert len(regular) == 1
