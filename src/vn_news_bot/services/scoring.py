from __future__ import annotations

import functools
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime

from loguru import logger
from underthesea import classify, word_tokenize

from vn_news_bot.config import (
    get_categories_config,
    get_nlp_category_map,
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


def _tokenize_vi(title: str) -> list[str]:
    """Segment Vietnamese title using underthesea word_tokenize.

    Returns lowercased tokens with underscores replaced by spaces
    so compound words like 'thủ_tướng' become 'thủ tướng' matching config keywords.
    """
    try:
        raw_tokens: list[str] = word_tokenize(title)
    except Exception:
        logger.debug("word_tokenize failed, falling back to simple split")
        raw_tokens = title.split()
    return [t.replace("_", " ").lower().strip() for t in raw_tokens if t.strip()]


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
    keywords_accented: frozenset[str]
    keywords_stripped: frozenset[str]


@functools.cache
def _build_category_matchers() -> tuple[_CategoryMatcher, ...]:
    """Build keyword sets (accented + stripped) for O(1) token lookup."""
    matchers: list[_CategoryMatcher] = []
    for cat in get_categories_config():
        accented: set[str] = set()
        stripped: set[str] = set()
        for kw in cat["keywords"]:
            accented.add(kw.lower())
            stripped.add(strip_accents(kw))
        matchers.append(
            _CategoryMatcher(
                name=cat["name"],
                emoji=cat["emoji"],
                boost=cat["boost"],
                keywords_accented=frozenset(accented),
                keywords_stripped=frozenset(stripped),
            )
        )
    return tuple(matchers)


def _classify_article(title: str) -> tuple[str, str, float]:
    tokens = _tokenize_vi(title)
    tokens_stripped = [strip_accents(t) for t in tokens]

    best: tuple[str, str, float] = ("Khác", "📋", 0.0)
    best_score = 0

    for cat in _build_category_matchers():
        match_count = 0
        for tok, tok_stripped in zip(tokens, tokens_stripped, strict=True):
            if tok in cat.keywords_accented or tok_stripped in cat.keywords_stripped:
                match_count += 1

        if match_count > best_score or (
            match_count == best_score and match_count > 0 and cat.boost > best[2]
        ):
            best = (cat.name, cat.emoji, cat.boost)
            best_score = match_count

    return best


def _classify_with_nlp(title: str) -> tuple[str, str, float] | None:
    """Use underthesea ML classifier as fallback, mapping to our categories."""
    try:
        result: str = classify(title)
    except Exception:
        logger.debug("underthesea classify failed for title: {}", title)
        return None
    nlp_map = get_nlp_category_map()
    mapped_name = nlp_map.get(result)
    if not mapped_name:
        return None
    for cat in get_categories_config():
        if cat["name"] == mapped_name:
            return cat["name"], cat["emoji"], cat["boost"]
    return None


def _classify_with_fallback(article: NewsArticle) -> tuple[str, str, float]:
    name, emoji, boost = _classify_article(article.title)
    if name != "Khác":
        return name, emoji, boost

    nlp_result = _classify_with_nlp(article.title)
    if nlp_result is not None:
        return nlp_result

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
