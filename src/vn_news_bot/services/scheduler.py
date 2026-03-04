from __future__ import annotations

from loguru import logger
from telegram.ext import ContextTypes

from vn_news_bot.adapters.telegram import (
    format_disaster_message,
    format_scored_news_message,
    format_weather_alert,
    format_weather_message,
)
from vn_news_bot.config import (
    get_weather_alert_humidity_change,
    get_weather_alert_temp_change,
)
from vn_news_bot.domain.models import WeatherReport
from vn_news_bot.services.disaster import get_disaster_alerts
from vn_news_bot.services.news import get_latest_news
from vn_news_bot.services.weather import get_weather_digest, get_weather_for_city


async def send_news_update(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.job or not context.job.chat_id:
        return

    bot_data = context.bot_data or {}
    newsapi_key = bot_data.get("newsapi_key", "")
    scored = await get_latest_news(newsapi_key=newsapi_key)
    message = format_scored_news_message(scored)

    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=message,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


async def send_weather_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.job or not context.job.chat_id:
        return

    bot_data = context.bot_data or {}
    api_key = bot_data.get("openweather_api_key", "")
    cities = bot_data.get("default_cities", ["Hanoi", "Ho Chi Minh City", "Da Nang"])

    reports = await get_weather_digest(cities, api_key)
    message = format_weather_message(reports)

    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=message,
        parse_mode="Markdown",
    )


async def send_weather_monitor(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.job or not context.job.chat_id:
        return

    bot_data = context.bot_data or {}
    api_key = bot_data.get("openweather_api_key", "")
    cities: list[str] = bot_data.get("default_cities", ["Hanoi", "Ho Chi Minh City", "Da Nang"])

    prev_weather: dict[str, WeatherReport] = bot_data.setdefault("_prev_weather", {})
    temp_threshold = get_weather_alert_temp_change()
    humidity_threshold = get_weather_alert_humidity_change()

    for city in cities:
        report = await get_weather_for_city(city, api_key)
        if not report:
            continue

        prev = prev_weather.get(city)
        if prev and _has_sudden_change(prev, report, temp_threshold, humidity_threshold):
            alert_msg = format_weather_alert(city, prev, report)
            await context.bot.send_message(
                chat_id=context.job.chat_id,
                text=alert_msg,
                parse_mode="Markdown",
            )
            logger.info("Weather alert sent for %s", city)

        prev_weather[city] = report


def _has_sudden_change(
    prev: WeatherReport,
    curr: WeatherReport,
    temp_threshold: float,
    humidity_threshold: int,
) -> bool:
    temp_diff = abs(curr.temperature - prev.temperature)
    humidity_diff = abs(curr.humidity - prev.humidity)
    return temp_diff >= temp_threshold or humidity_diff >= humidity_threshold


async def send_disaster_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.job or not context.job.chat_id:
        return

    alerts = await get_disaster_alerts()
    if not alerts:
        return

    message = format_disaster_message(alerts)
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=message,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )
