from __future__ import annotations

import json

from llm_zingplay import ZingPlayChat
from loguru import logger

from vn_news_bot.domain.models import ArticleClassification

_SYSTEM_PROMPT = (
    "Classify Vietnamese news. Reply JSON only.\n"
    'disaster: none|low|medium|high (real natural disasters only, not metaphors like "bão giá")\n'
    "hot: true if breaking/major news"
)

_VALID_SEVERITIES = {"none", "low", "medium", "high"}


class LLMClassifier:
    """Classifies news articles using ZingPlay LLM."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
    ) -> None:
        self._client = ZingPlayChat(api_key=api_key, base_url=base_url)
        self._model = model
        self._timeout = timeout

    def classify_article(self, title: str) -> ArticleClassification:
        try:
            raw = self._client.chat(
                title,
                model=self._model,
                system=_SYSTEM_PROMPT,
                temperature=0.0,
            )
            return _parse_response(raw)
        except Exception:
            logger.warning("LLM classification failed for: {}", title)
            return ArticleClassification()


def _parse_response(raw: str) -> ArticleClassification:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("LLM returned invalid JSON: {}", raw)
        return ArticleClassification()

    severity = data.get("disaster", "none")
    if severity not in _VALID_SEVERITIES:
        logger.warning("LLM returned invalid severity: {}", severity)
        return ArticleClassification()

    is_hot = bool(data.get("hot", False))
    return ArticleClassification(disaster_severity=severity, is_hot=is_hot)
