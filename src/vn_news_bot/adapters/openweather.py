from __future__ import annotations

import html
import re
import unicodedata
from typing import Any

import httpx
from loguru import logger

from vn_news_bot.config import get_cities
from vn_news_bot.domain.models import DailyForecast, WeatherReport

THOITIET_BASE_URL = "https://thoitiet.vn"
ACCUWEATHER_BASE_URL = "https://www.accuweather.com/vi/vn"
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


async def fetch_weather(city: str, api_key: str = "") -> WeatherReport | None:
    city_config = get_cities().get(city)
    if city_config:
        report = await _fetch_thoitiet(city, city_config)
        if report:
            return report
        logger.info("thoitiet.vn failed for {}, trying AccuWeather", city)
        return await _fetch_accuweather(city, city_config)

    return await _fetch_thoitiet_by_slug(city)


def _to_slug(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower().strip()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")


async def _fetch_thoitiet_by_slug(city: str) -> WeatherReport | None:
    slug = _to_slug(city)
    if not slug:
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{THOITIET_BASE_URL}/{slug}")
            response.raise_for_status()
            return _parse_thoitiet_html(response.text, city)
    except httpx.HTTPError:
        logger.warning("Failed to fetch from thoitiet.vn for custom city {}", city)
        return None


async def _fetch_thoitiet(city: str, config: dict[str, Any]) -> WeatherReport | None:
    slug = config.get("slug")
    if not slug:
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{THOITIET_BASE_URL}/{slug}")
            response.raise_for_status()
            return _parse_thoitiet_html(response.text, city)
    except httpx.HTTPError:
        logger.warning("Failed to fetch from thoitiet.vn for {}", city)
        return None


async def _fetch_accuweather(city: str, config: dict[str, Any]) -> WeatherReport | None:
    accu_id = config.get("accuweather_id")
    if not accu_id:
        return None

    slug = city.lower().replace(" ", "-")
    url = f"{ACCUWEATHER_BASE_URL}/{slug}/{accu_id}/current-weather/{accu_id}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers={"User-Agent": _BROWSER_UA})
            response.raise_for_status()
            return _parse_accuweather_html(response.text, city)
    except httpx.HTTPError:
        logger.warning("Failed to fetch from AccuWeather for {}", city)
        return None


def _parse_thoitiet_html(text: str, city: str) -> WeatherReport | None:
    temp_match = re.search(r'class="current-temperature"[^>]*>([\d.]+)°', text)
    if not temp_match:
        return None

    temperature = float(temp_match.group(1))

    feels_match = re.search(r"Cảm giác như ([\d.]+)°", text)
    feels_like = float(feels_match.group(1)) if feels_match else temperature

    desc_match = re.search(
        r'class="overview-caption-item overview-caption-item-detail"[^>]*>([^<]+)<',
        text,
    )
    description = desc_match.group(1).strip() if desc_match else ""

    humidity_match = re.search(r"Độ ẩm.*?(\d+)%", text, re.DOTALL)
    humidity = int(humidity_match.group(1)) if humidity_match else 0

    wind_match = re.search(r"Gió.*?([\d.]+)\s*km/giờ", text, re.DOTALL)
    wind_kmh = float(wind_match.group(1)) if wind_match else 0.0

    return WeatherReport(
        city=city,
        temperature=temperature,
        feels_like=feels_like,
        humidity=humidity,
        description=description,
        wind_speed=wind_kmh / 3.6,
    )


def _parse_accuweather_html(text: str, city: str) -> WeatherReport | None:
    decoded = html.unescape(text)

    temp_match = re.search(r'class="display-temp">(\d+)°', decoded)
    if not temp_match:
        return None

    temperature = float(temp_match.group(1))

    feels_match = re.search(r"RealFeel®\s*(\d+)°", decoded)
    feels_like = float(feels_match.group(1)) if feels_match else temperature

    desc_match = re.search(r'class="phrase">([^<]+)<', decoded)
    description = desc_match.group(1).strip() if desc_match else ""

    humidity_match = re.search(r"Độ ẩm.*?(\d+)%", decoded, re.DOTALL)
    humidity = int(humidity_match.group(1)) if humidity_match else 0

    wind_match = re.search(r"Gió.*?(\d+)\s*km/h", decoded, re.DOTALL)
    wind_kmh = float(wind_match.group(1)) if wind_match else 0.0

    return WeatherReport(
        city=city,
        temperature=temperature,
        feels_like=feels_like,
        humidity=humidity,
        description=description,
        wind_speed=wind_kmh / 3.6,
    )


async def fetch_7day_forecast(city: str) -> list[DailyForecast]:
    city_config = get_cities().get(city)
    slug = city_config.get("slug") if city_config else _to_slug(city)
    if not slug:
        return []

    url = f"{THOITIET_BASE_URL}/{slug}/7-ngay-toi"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return _parse_7day_html(response.text)
    except httpx.HTTPError:
        logger.warning("Failed to fetch 7-day forecast for {}", city)
        return []


def _parse_7day_html(text: str) -> list[DailyForecast]:
    days = re.findall(
        r'class="summary-day">\s*<span>([^<]+)</span>',
        text,
    )
    mins = re.findall(
        r'class="summary-temperature-min">\s*([\d.]+)°C',
        text,
    )
    maxs = re.findall(
        r'class="summary-temperature-max-value">\s*([\d.]+)°C',
        text,
    )
    descs = re.findall(
        r'class="summary-description-detail">\s*([^<]+)',
        text,
    )

    forecasts: list[DailyForecast] = []
    for i in range(min(len(days), len(mins), len(maxs))):
        desc = descs[i].strip() if i < len(descs) else ""
        forecasts.append(
            DailyForecast(
                day_label=days[i].strip(),
                temp_min=float(mins[i]),
                temp_max=float(maxs[i]),
                description=desc,
            )
        )

    return forecasts
