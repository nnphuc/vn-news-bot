from __future__ import annotations

from datetime import UTC, datetime, timedelta

from vn_news_bot.domain.models import NewsArticle, ScoreBreakdown, ScoredArticle
from vn_news_bot.services.scoring import (
    _classify_article,
    _find_clusters,
    _jaccard_similarity,
    _normalize_title,
    _tokenize,
    score_articles,
)


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


class TestClassifyArticle:
    def test_politics(self) -> None:
        name, emoji, _boost = _classify_article("Thủ tướng họp bàn chính sách mới")
        assert name == "Thời sự"
        assert emoji == "📌"

    def test_economy(self) -> None:
        name, emoji, _boost = _classify_article("VN-Index vượt mốc 1400 điểm chứng khoán")
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
            _make_article(
                "Thủ tướng gặp Tổng thống Mỹ tại Hà Nội", "VnExpress", hours_ago=1
            ),
            _make_article(
                "Thủ tướng gặp gỡ Tổng thống Mỹ tại Hà Nội", "Tuổi Trẻ", hours_ago=1
            ),
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
            _make_article("Chứng khoán VN-Index tăng điểm", "VnEconomy", hours_ago=1),
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
