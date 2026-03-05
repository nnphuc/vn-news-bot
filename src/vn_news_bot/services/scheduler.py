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


def _get_chat_ids(context: ContextTypes.DEFAULT_TYPE) -> set[int]:
    ids: set[int] = (context.bot_data or {}).get("_chat_ids", set())
    return ids


async def send_news_update(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_ids = _get_chat_ids(context)
    if not chat_ids:
        return

    bot_data = context.bot_data or {}
    newsapi_key = bot_data.get("newsapi_key", "")
    scored = await get_latest_news(newsapi_key=newsapi_key)
    message = format_scored_news_message(scored)

    for chat_id in chat_ids:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        except Exception:
            logger.warning("Failed to send news update to chat {}", chat_id)


async def send_weather_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_ids = _get_chat_ids(context)
    if not chat_ids:
        return

    bot_data = context.bot_data or {}
    api_key = bot_data.get("openweather_api_key", "")
    cities = bot_data.get("default_cities", ["Hanoi", "Ho Chi Minh City", "Da Nang"])

    reports = await get_weather_digest(cities, api_key)
    message = format_weather_message(reports)

    for chat_id in chat_ids:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="Markdown",
            )
        except Exception:
            logger.warning("Failed to send weather digest to chat {}", chat_id)


async def send_weather_monitor(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_ids = _get_chat_ids(context)
    if not chat_ids:
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
            for chat_id in chat_ids:
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=alert_msg,
                        parse_mode="Markdown",
                    )
                except Exception:
                    logger.warning("Failed to send weather alert to chat {}", chat_id)
            logger.info("Weather alert sent for {}", city)

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

    bot_data = context.bot_data or {}
    sent_urls: set[str] = bot_data.setdefault("_sent_disaster_urls", set())
    new_alerts = [a for a in alerts if a.url not in sent_urls]
    if not new_alerts:
        return

    message = format_disaster_message(new_alerts)
    try:
        await context.bot.send_message(
            chat_id=context.job.chat_id,
            text=message,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        sent_urls.update(a.url for a in new_alerts)
        # Keep only last 500 URLs to prevent unbounded growth
        if len(sent_urls) > 500:
            bot_data["_sent_disaster_urls"] = set(list(sent_urls)[-300:])
    except Exception:
        logger.warning("Failed to send disaster alert to chat {}", context.job.chat_id)
