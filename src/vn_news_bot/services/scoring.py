from __future__ import annotations

import functools
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime

from vn_news_bot.config import (
    get_categories_config,
    get_recency_config,
    get_rss_category_map,
    get_scoring_limits,
    get_scoring_weights,
    get_source_trust,
    get_stopwords,
    get_trending_config,
)
from vn_news_bot.domain.models import (
    NewsArticle,
    ScoreBreakdown,
    ScoredArticle,
)
from vn_news_bot.utils.text import strip_accents


def _normalize_title(title: str) -> str:
    text = title.lower().strip()
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokenize(text: str, stopwords: set[str]) -> set[str]:
    syllables = [w for w in text.split() if w not in stopwords and len(w) > 1]
    tokens = set(syllables)
    for i in range(len(syllables) - 1):
        tokens.add(f"{syllables[i]} {syllables[i + 1]}")
    return tokens


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


def _find_clusters(
    articles: list[NewsArticle],
    stopwords: set[str],
    threshold: float,
) -> list[list[int]]:
    normalized = [_normalize_title(a.title) for a in articles]
    token_sets = [_tokenize(t, stopwords) for t in normalized]

    inverted: dict[str, list[int]] = {}
    for idx, tokens in enumerate(token_sets):
        for token in tokens:
            inverted.setdefault(token, []).append(idx)

    candidates: set[tuple[int, int]] = set()
    for indices in inverted.values():
        if 2 <= len(indices) <= 50:
            for i in range(len(indices)):
                for j in range(i + 1, len(indices)):
                    candidates.add((indices[i], indices[j]))

    adj: dict[int, set[int]] = {}
    for i, j in candidates:
        sim = _jaccard_similarity(token_sets[i], token_sets[j])
        if sim >= threshold:
            adj.setdefault(i, set()).add(j)
            adj.setdefault(j, set()).add(i)

    visited: set[int] = set()
    clusters: list[list[int]] = []
    for node in adj:
        if node in visited:
            continue
        component: list[int] = []
        stack = [node]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            stack.extend(adj.get(current, set()) - visited)
        clusters.append(sorted(component))

    return clusters


def _compute_recency(article: NewsArticle, now: datetime) -> float:
    config = get_recency_config()
    half_life = config["half_life_hours"]
    decay = config["decay_constant"]
    age_hours = max(0.0, (now - article.published).total_seconds() / 3600)
    return math.exp(-decay * age_hours / half_life)


def _compute_source_trust(source: str) -> float:
    trust_map = get_source_trust()
    return trust_map.get(source, trust_map.get("default", 0.5))


@dataclass(frozen=True)
class _CategoryMatcher:
    name: str
    emoji: str
    boost: float
    exact_keywords: list[tuple[str, str]]  # (keyword, stripped_keyword)
    regex_patterns: list[tuple[re.Pattern[str], re.Pattern[str]]]  # (accented, stripped)


@functools.cache
def _build_category_matchers() -> tuple[_CategoryMatcher, ...]:
    """Pre-compile keyword patterns and strip accents once at config load."""
    matchers: list[_CategoryMatcher] = []
    for cat in get_categories_config():
        exact: list[tuple[str, str]] = []
        regex: list[tuple[re.Pattern[str], re.Pattern[str]]] = []
        for kw in cat["keywords"]:
            stripped_kw = strip_accents(kw)
            if len(kw) <= 3:
                regex.append(
                    (
                        re.compile(r"\b" + re.escape(kw) + r"\b"),
                        re.compile(r"\b" + re.escape(stripped_kw) + r"\b"),
                    )
                )
            else:
                exact.append((kw, stripped_kw))
        matchers.append(
            _CategoryMatcher(
                name=cat["name"],
                emoji=cat["emoji"],
                boost=cat["boost"],
                exact_keywords=exact,
                regex_patterns=regex,
            )
        )
    return tuple(matchers)


def _classify_article(title: str) -> tuple[str, str, float]:
    lower_title = _normalize_title(title)
    stripped_title = strip_accents(lower_title)

    best: tuple[str, str, float] = ("Khác", "📋", 0.0)
    best_score = 0

    for cat in _build_category_matchers():
        match_count = 0
        for kw, stripped_kw in cat.exact_keywords:
            if kw in lower_title or stripped_kw in stripped_title:
                match_count += 1
        for accented_pat, stripped_pat in cat.regex_patterns:
            if accented_pat.search(lower_title) or stripped_pat.search(stripped_title):
                match_count += 1

        if match_count > best_score or (
            match_count == best_score and match_count > 0 and cat.boost > best[2]
        ):
            best = (cat.name, cat.emoji, cat.boost)
            best_score = match_count

    return best


def _classify_with_fallback(article: NewsArticle) -> tuple[str, str, float]:
    name, emoji, boost = _classify_article(article.title)
    if name != "Khác":
        return name, emoji, boost
    if article.category:
        rss_map = get_rss_category_map()
        mapped_name = rss_map.get(article.category.lower())
        if mapped_name:
            for cat in get_categories_config():
                if cat["name"] == mapped_name:
                    return cat["name"], cat["emoji"], cat["boost"]
        for cat in get_categories_config():
            if cat["name"].lower() in article.category.lower():
                return cat["name"], cat["emoji"], cat["boost"]
    return "Khác", "📋", 0.0


def score_articles(
    articles: list[NewsArticle],
    now: datetime | None = None,
    max_items: int = 10,
) -> list[ScoredArticle]:
    if not articles:
        return []

    if now is None:
        now = datetime.now(UTC)

    weights = get_scoring_weights()
    trending_config = get_trending_config()
    stopwords = set(get_stopwords())
    limits = get_scoring_limits()
    threshold = trending_config["similarity_threshold"]
    max_divisor = trending_config["max_source_divisor"]

    clusters = _find_clusters(articles, stopwords, threshold)

    article_cluster: dict[int, list[int]] = {}
    for cluster in clusters:
        for idx in cluster:
            article_cluster[idx] = cluster

    # For each cluster, find the best article (highest source trust)
    # and mark others as duplicates to skip
    cluster_best: dict[int, int] = {}  # cluster_id (first idx) -> best article idx
    skip_indices: set[int] = set()
    for cluster in clusters:
        cluster_id = cluster[0]
        best_idx = max(cluster, key=lambda i: _compute_source_trust(articles[i].source))
        cluster_best[cluster_id] = best_idx
        for idx in cluster:
            if idx != best_idx:
                skip_indices.add(idx)

    scored: list[ScoredArticle] = []
    for idx, article in enumerate(articles):
        if idx in skip_indices:
            continue

        recency = _compute_recency(article, now)
        source_trust = _compute_source_trust(article.source)
        cat_name, cat_emoji, keyword_boost = _classify_with_fallback(article)

        cluster = article_cluster.get(idx, [])
        trending_sources: list[str] = []
        trending_score = 0.0
        if cluster:
            sources_in_cluster = sorted({articles[i].source for i in cluster})
            source_count = len(sources_in_cluster)
            if source_count >= trending_config["min_sources"]:
                trending_score = min(1.0, (source_count - 1) / max_divisor)
                trending_sources = sources_in_cluster

        total = (
            weights["recency"] * recency
            + weights["source_trust"] * source_trust
            + weights["trending"] * trending_score
            + weights["keyword_boost"] * keyword_boost
        )

        breakdown = ScoreBreakdown(
            recency=recency,
            source_trust=source_trust,
            trending=trending_score,
            keyword_boost=keyword_boost,
        )

        scored.append(
            ScoredArticle(
                article=article,
                score=total,
                category=cat_name,
                category_emoji=cat_emoji,
                trending_sources=trending_sources,
                breakdown=breakdown,
            )
        )

    scored.sort(key=lambda s: s.score, reverse=True)

    trending = [s for s in scored if s.is_trending][: limits["max_trending_items"]]
    trending_urls = {s.article.url for s in trending}
    remaining = max_items - len(trending)
    others = [s for s in scored if s.article.url not in trending_urls][:remaining]

    return trending + others
