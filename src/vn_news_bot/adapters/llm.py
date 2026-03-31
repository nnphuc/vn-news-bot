from __future__ import annotations

import json
from typing import Any

from loguru import logger
from openai import OpenAI

from vn_news_bot.domain.models import ArticleClassification

_SYSTEM_PROMPT = (
    "/no_think\n"
    "Classify Vietnamese news. Reply JSON only.\n"
    'disaster: none|low|medium|high (real natural disasters only, not metaphors like "bão giá")\n'
    "hot: true if breaking/major news"
)

_VALID_SEVERITIES = {"none", "low", "medium", "high"}


class LLMClassifier:
    """Classifies news articles using OpenAI-compatible LLM."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
    ) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self._model = model
        self._timeout = timeout

    def classify_article(self, title: str) -> ArticleClassification:
        try:
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": title},
            ]
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.0,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            raw = response.choices[0].message.content or ""
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
