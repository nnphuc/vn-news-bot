from __future__ import annotations

from unittest.mock import patch

from vn_news_bot.config import get_llm_api_key, get_llm_base_url, get_llm_model, get_llm_timeout


def test_llm_config_defaults() -> None:
    with patch.dict(
        "os.environ",
        {"TELEGRAM_BOT_TOKEN": "test", "LLM_API_KEY": "test-key"},
        clear=False,
    ):
        assert get_llm_api_key() == "test-key"
        assert get_llm_base_url() == "https://chat.zingplay.com/api"
        assert get_llm_model() == "local-model"
        assert get_llm_timeout() == 15.0


def test_llm_config_custom() -> None:
    with patch.dict(
        "os.environ",
        {
            "TELEGRAM_BOT_TOKEN": "test",
            "LLM_API_KEY": "custom-key",
            "LLM_BASE_URL": "http://localhost:8000",
            "LLM_MODEL": "my-model",
            "LLM_TIMEOUT": "30",
        },
        clear=False,
    ):
        from vn_news_bot.config import Settings

        s = Settings()  # type: ignore[call-arg]
        assert s.llm_api_key == "custom-key"
        assert s.llm_base_url == "http://localhost:8000"
        assert s.llm_model == "my-model"
        assert s.llm_timeout == 30.0
