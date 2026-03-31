from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from vn_news_bot.adapters.llm import LLMClassifier

SYSTEM_PROMPT = (
    "Classify Vietnamese news. Reply JSON only.\n"
    'disaster: none|low|medium|high (real natural disasters only, not metaphors like "bão giá")\n'
    "hot: true if breaking/major news"
)


@pytest.fixture
def classifier() -> LLMClassifier:
    return LLMClassifier(
        api_key="test-key",
        base_url="http://localhost:8000",
        model="test-model",
        timeout=5.0,
    )


class TestClassifyArticle:
    def test_disaster_high(self, classifier: LLMClassifier) -> None:
        mock_client = MagicMock()
        mock_client.chat.return_value = json.dumps({"disaster": "high", "hot": True})
        classifier._client = mock_client

        result = classifier.classify_article("Bão số 5 đổ bộ miền Trung gây thiệt hại lớn")

        assert result.disaster_severity == "high"
        assert result.is_hot is True
        mock_client.chat.assert_called_once_with(
            "Bão số 5 đổ bộ miền Trung gây thiệt hại lớn",
            model="test-model",
            system=SYSTEM_PROMPT,
            temperature=0.0,
        )

    def test_no_disaster_not_hot(self, classifier: LLMClassifier) -> None:
        mock_client = MagicMock()
        mock_client.chat.return_value = json.dumps({"disaster": "none", "hot": False})
        classifier._client = mock_client

        result = classifier.classify_article("Thời tiết đẹp cuối tuần")

        assert result.disaster_severity == "none"
        assert result.is_hot is False

    def test_metaphorical_storm_not_flagged(self, classifier: LLMClassifier) -> None:
        mock_client = MagicMock()
        mock_client.chat.return_value = json.dumps({"disaster": "none", "hot": False})
        classifier._client = mock_client

        result = classifier.classify_article("Doanh nghiệp vượt bão giá xăng dầu")

        assert result.disaster_severity == "none"
        assert result.is_hot is False

    def test_invalid_json_returns_safe_default(self, classifier: LLMClassifier) -> None:
        mock_client = MagicMock()
        mock_client.chat.return_value = "not json at all"
        classifier._client = mock_client

        result = classifier.classify_article("Some title")

        assert result.disaster_severity == "none"
        assert result.is_hot is False

    def test_exception_returns_safe_default(self, classifier: LLMClassifier) -> None:
        mock_client = MagicMock()
        mock_client.chat.side_effect = RuntimeError("connection failed")
        classifier._client = mock_client

        result = classifier.classify_article("Some title")

        assert result.disaster_severity == "none"
        assert result.is_hot is False

    def test_missing_fields_use_defaults(self, classifier: LLMClassifier) -> None:
        mock_client = MagicMock()
        mock_client.chat.return_value = json.dumps({"disaster": "low"})
        classifier._client = mock_client

        result = classifier.classify_article("Mưa lớn tại Hà Nội")

        assert result.disaster_severity == "low"
        assert result.is_hot is False

    def test_invalid_severity_returns_safe_default(self, classifier: LLMClassifier) -> None:
        mock_client = MagicMock()
        mock_client.chat.return_value = json.dumps({"disaster": "EXTREME", "hot": True})
        classifier._client = mock_client

        result = classifier.classify_article("Some title")

        assert result.disaster_severity == "none"
        assert result.is_hot is False
