from __future__ import annotations

import functools
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    telegram_bot_token: str
    openweather_api_key: str
    newsapi_key: str = ""
    default_cities: list[str] = ["Hanoi", "Ho Chi Minh City", "Da Nang"]
    log_level: str = "INFO"


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def _load_yaml(filename: str) -> dict[str, Any]:
    path = CONFIG_DIR / filename
    with path.open(encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f)
    return data


@functools.cache
def load_feeds_config() -> dict[str, Any]:
    return _load_yaml("feeds.yaml")


@functools.cache
def load_cities_config() -> dict[str, Any]:
    return _load_yaml("cities.yaml")


@functools.cache
def load_disaster_config() -> dict[str, Any]:
    return _load_yaml("disaster.yaml")


@functools.cache
def load_schedule_config() -> dict[str, Any]:
    return _load_yaml("schedule.yaml")


def get_rss_feeds() -> dict[str, str]:
    return cast(dict[str, str], load_feeds_config()["rss"])


def get_newsapi_base_url() -> str:
    return cast(str, load_feeds_config()["newsapi"]["base_url"])


def get_max_news_items() -> int:
    return cast(int, load_feeds_config()["limits"]["max_news_items"])


def get_cities() -> dict[str, dict[str, Any]]:
    return cast(dict[str, dict[str, Any]], load_cities_config()["cities"])


def get_city_aliases() -> dict[str, str]:
    return cast(dict[str, str], load_cities_config()["aliases"])


def get_disaster_keywords() -> list[str]:
    return cast(list[str], load_disaster_config()["keywords"])


def get_critical_keywords() -> list[str]:
    return cast(list[str], load_disaster_config()["critical_keywords"])


def get_max_disaster_items() -> int:
    return cast(int, load_disaster_config()["limits"]["max_disaster_items"])


def get_schedule_timezone() -> str:
    return cast(str, load_schedule_config()["timezone"])


def get_news_schedule() -> list[dict[str, int]]:
    return cast(list[dict[str, int]], load_schedule_config()["news"]["schedule"])


def get_weather_digest_hour() -> int:
    return cast(int, load_schedule_config()["weather"]["digest_hour"])


def get_weather_digest_minute() -> int:
    return cast(int, load_schedule_config()["weather"]["digest_minute"])


def get_weather_monitor_interval() -> int:
    return cast(int, load_schedule_config()["weather"]["monitor_interval_minutes"])


def get_weather_alert_temp_change() -> float:
    return cast(float, load_schedule_config()["weather"]["alert_temp_change"])


def get_weather_alert_humidity_change() -> int:
    return cast(int, load_schedule_config()["weather"]["alert_humidity_change"])


def get_disaster_check_interval() -> int:
    return cast(int, load_schedule_config()["disaster"]["check_interval_minutes"])


@functools.cache
def load_scoring_config() -> dict[str, Any]:
    return _load_yaml("scoring.yaml")


def get_scoring_weights() -> dict[str, float]:
    return cast(dict[str, float], load_scoring_config()["weights"])


def get_recency_config() -> dict[str, float]:
    return cast(dict[str, float], load_scoring_config()["recency"])


def get_source_trust() -> dict[str, float]:
    return cast(dict[str, float], load_scoring_config()["source_trust"])


def get_trending_config() -> dict[str, Any]:
    return cast(dict[str, Any], load_scoring_config()["trending"])


def get_categories_config() -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], load_scoring_config()["categories"])


def get_stopwords() -> list[str]:
    return cast(list[str], load_scoring_config()["stopwords"])


def get_display_categories() -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], load_scoring_config()["display_categories"])


def get_scoring_limits() -> dict[str, int]:
    return cast(dict[str, int], load_scoring_config()["limits"])
