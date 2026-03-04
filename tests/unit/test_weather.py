from __future__ import annotations

from vn_news_bot.adapters.telegram import format_single_weather, format_weather_message
from vn_news_bot.config import get_cities, get_city_aliases
from vn_news_bot.domain.models import WeatherReport
from vn_news_bot.handlers.commands import _resolve_city


def test_resolve_city_exact_match() -> None:
    assert _resolve_city("Hanoi") == "Hanoi"
    assert _resolve_city("Da Nang") == "Da Nang"


def test_resolve_city_alias() -> None:
    assert _resolve_city("hà nội") == "Hanoi"
    assert _resolve_city("hcm") == "Ho Chi Minh City"
    assert _resolve_city("sài gòn") == "Ho Chi Minh City"


def test_resolve_city_unknown() -> None:
    assert _resolve_city("Paris") is None
    assert _resolve_city("") is None


def test_all_aliases_resolve_to_valid_cities() -> None:
    cities = get_cities()
    for alias, city in get_city_aliases().items():
        assert city in cities, f"Alias '{alias}' maps to unknown city '{city}'"


def test_format_single_weather(sample_weather: WeatherReport) -> None:
    text = format_single_weather(sample_weather)
    assert "Hanoi" in text
    assert "28°C" in text


def test_format_weather_message_empty() -> None:
    assert "Không có" in format_weather_message([])


def test_format_weather_message(sample_weather: WeatherReport) -> None:
    text = format_weather_message([sample_weather])
    assert "Hanoi" in text
    assert "Dự báo thời tiết" in text
