from __future__ import annotations

import asyncio

from loguru import logger

from vn_news_bot.adapters.openweather import fetch_7day_forecast, fetch_weather
from vn_news_bot.domain.models import DailyForecast, WeatherReport


async def get_weather_for_city(city: str, api_key: str = "") -> WeatherReport | None:
    return await fetch_weather(city, api_key)


async def get_forecast_for_city(city: str) -> list[DailyForecast]:
    return await fetch_7day_forecast(city)


async def get_weather_digest(cities: list[str], api_key: str) -> list[WeatherReport]:
    tasks = [fetch_weather(city, api_key) for city in cities]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    reports: list[WeatherReport] = []
    for result in results:
        if isinstance(result, WeatherReport):
            reports.append(result)
        elif isinstance(result, Exception):
            logger.warning("Weather fetch failed: %s", result)

    return reports


def get_weather_suggestion(report: WeatherReport, description_lower: str = "") -> str:
    desc = description_lower or report.description.lower()
    tips: list[str] = []

    if report.temperature >= 35:
        tips.append("Mặc đồ thoáng mát, uống nhiều nước")
    elif report.temperature >= 28:
        tips.append("Mặc đồ nhẹ, thoáng")
    elif report.temperature >= 20:
        tips.append("Mặc áo dài tay hoặc áo khoác nhẹ")
    elif report.temperature >= 15:
        tips.append("Mặc áo ấm, khoác ngoài")
    else:
        tips.append("Mặc nhiều lớp, giữ ấm")

    rain_keywords = ("mưa", "rain", "giông", "dông")
    if any(k in desc for k in rain_keywords):
        tips.append("Mang ô/áo mưa")

    if report.humidity >= 85:
        tips.append("Độ ẩm cao, dễ bí bách")

    if report.wind_speed >= 8:
        tips.append("Gió mạnh, cẩn thận khi ra ngoài")

    return " | ".join(tips)


def get_forecast_suggestion(forecast: DailyForecast) -> str:
    tips: list[str] = []
    desc = forecast.description.lower()

    if forecast.temp_max >= 35:
        tips.append("Nóng")
    elif forecast.temp_min <= 15:
        tips.append("Lạnh, giữ ấm")

    rain_keywords = ("mưa", "rain", "giông", "dông")
    if any(k in desc for k in rain_keywords):
        tips.append("Mang ô")

    return " | ".join(tips) if tips else ""
