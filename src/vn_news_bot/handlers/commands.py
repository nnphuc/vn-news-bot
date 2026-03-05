from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes

from vn_news_bot.adapters.telegram import (
    format_disaster_message,
    format_forecast_message,
    format_scored_news_message,
    format_single_weather,
)
from vn_news_bot.config import (
    get_cities,
    get_city_aliases,
    get_disaster_check_interval,
)
from vn_news_bot.services.disaster import get_disaster_alerts
from vn_news_bot.services.news import get_latest_news
from vn_news_bot.services.scheduler import send_disaster_check
from vn_news_bot.services.weather import get_forecast_for_city, get_weather_for_city
from vn_news_bot.utils.text import strip_accents

_ERROR_MSG = "Có lỗi xảy ra, vui lòng thử lại sau."
_SEARCH_POOL_SIZE = 200
_MAX_FILTERED_ITEMS = 10

_Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]


def _safe_handler(func: _Handler) -> _Handler:
    """Wrap a command handler with try/except for external API errors."""

    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            await func(update, context)
        except Exception:
            logger.exception("Error in {}", func.__name__)
            if update.effective_message:
                await update.effective_message.reply_text(_ERROR_MSG)

    wrapper.__name__ = func.__name__
    return wrapper


def _get_newsapi_key(context: ContextTypes.DEFAULT_TYPE) -> str:
    key: str = (context.bot_data or {}).get("newsapi_key", "")
    return key


def _build_help_text() -> str:
    cities = get_cities()
    return (
        "🇻🇳 *VN News Bot*\n\n"
        "*📰 Tin tức:*\n"
        "/news - Tin tức mới nhất\n"
        "/trending - Tin nổi bật\n"
        "/thoisu - Thời sự & pháp luật\n"
        "/kinhte - Kinh tế\n"
        "/chungkhoan - Chứng khoán\n"
        "/quocte - Quốc tế\n"
        "/thethao - Thể thao\n"
        "/congnghe - Công nghệ\n"
        "/search <từ khóa> - Tìm tin\n\n"
        "*🌤 Thời tiết:*\n"
        "/weather - Thời tiết (mặc định: Hanoi)\n"
        "/weather <city> - Thời tiết thành phố\n"
        "/forecast <city> - Dự báo 7 ngày\n\n"
        "*⚠️ Cảnh báo:*\n"
        "/disaster - Cảnh báo thiên tai\n"
        "/subscribe - Đăng ký cảnh báo thiên tai\n"
        "/unsubscribe - Hủy đăng ký cảnh báo\n\n"
        f"*Thành phố hỗ trợ:* {', '.join(cities.keys())}"
    )


def _resolve_city(name: str) -> str | None:
    cities = get_cities()
    stripped = name.strip()
    if stripped in cities:
        return stripped
    lower = stripped.lower()
    for key in cities:
        if key.lower() == lower:
            return key
    return get_city_aliases().get(lower)


@_safe_handler
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_chat:
        return

    chat_ids: set[int] = context.bot_data.setdefault("_chat_ids", set())
    chat_ids.add(update.effective_chat.id)

    await update.effective_message.reply_text(_build_help_text(), parse_mode="Markdown")


@_safe_handler
async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    scored = await get_latest_news(newsapi_key=_get_newsapi_key(context))
    message = format_scored_news_message(scored)
    await update.effective_message.reply_text(
        message, parse_mode="Markdown", disable_web_page_preview=True
    )


async def _category_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    categories: list[str],
    empty_msg: str,
) -> None:
    if not update.effective_message:
        return

    scored = await get_latest_news(
        newsapi_key=_get_newsapi_key(context), max_items=_SEARCH_POOL_SIZE
    )
    cat_set = set(categories)
    filtered = [s for s in scored if s.category in cat_set][:_MAX_FILTERED_ITEMS]
    message = format_scored_news_message(filtered) if filtered else empty_msg
    await update.effective_message.reply_text(
        message, parse_mode="Markdown", disable_web_page_preview=True
    )


@_safe_handler
async def sports_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _category_command(update, context, ["Thể thao"], "Không có tin thể thao.")


@_safe_handler
async def economy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _category_command(update, context, ["Kinh tế", "Chứng khoán"], "Không có tin kinh tế.")


@_safe_handler
async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _category_command(update, context, ["Chứng khoán"], "Không có tin chứng khoán.")


@_safe_handler
async def international_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _category_command(update, context, ["Quốc tế"], "Không có tin quốc tế.")


@_safe_handler
async def politics_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _category_command(update, context, ["Thời sự", "Pháp luật"], "Không có tin thời sự.")


@_safe_handler
async def tech_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _category_command(update, context, ["Công nghệ"], "Không có tin công nghệ.")


@_safe_handler
async def trending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    scored = await get_latest_news(
        newsapi_key=_get_newsapi_key(context), max_items=_SEARCH_POOL_SIZE
    )
    hot = [s for s in scored if s.is_trending][:_MAX_FILTERED_ITEMS]
    message = format_scored_news_message(hot) if hot else "Không có tin nổi bật."
    await update.effective_message.reply_text(
        message, parse_mode="Markdown", disable_web_page_preview=True
    )


@_safe_handler
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    if not context.args:
        await update.effective_message.reply_text("Dùng: /search <từ khóa>")
        return

    keyword = " ".join(context.args).lower()
    keyword_no_accent = strip_accents(keyword)

    scored = await get_latest_news(
        newsapi_key=_get_newsapi_key(context), max_items=_SEARCH_POOL_SIZE
    )
    results = [
        s
        for s in scored
        if keyword in s.article.title.lower() or keyword_no_accent in strip_accents(s.article.title)
    ][:_MAX_FILTERED_ITEMS]
    if results:
        message = format_scored_news_message(results)
    else:
        message = f"Không tìm thấy tin về '{keyword}'."
    await update.effective_message.reply_text(
        message, parse_mode="Markdown", disable_web_page_preview=True
    )


@_safe_handler
async def forecast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    city_input = "Hanoi" if not context.args else " ".join(context.args)
    city = _resolve_city(city_input)
    if not city:
        cities = get_cities()
        await update.effective_message.reply_text(
            f"Không tìm thấy thành phố '{city_input}'.\n"
            f"Thành phố có sẵn: {', '.join(cities.keys())}"
        )
        return

    forecast = await get_forecast_for_city(city)
    if forecast:
        await update.effective_message.reply_text(
            format_forecast_message(city, forecast), parse_mode="Markdown"
        )
    else:
        await update.effective_message.reply_text(f"Không tìm thấy dự báo cho '{city}'.")


@_safe_handler
async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    city_input = "Hanoi" if not context.args else " ".join(context.args)
    city = _resolve_city(city_input)
    if not city:
        cities = get_cities()
        await update.effective_message.reply_text(
            f"Không tìm thấy thành phố '{city_input}'.\n"
            f"Thành phố có sẵn: {', '.join(cities.keys())}"
        )
        return

    bot_data = context.bot_data or {}
    api_key = bot_data.get("openweather_api_key", "")
    report = await get_weather_for_city(city, api_key)

    if report:
        forecast = await get_forecast_for_city(city)
        await update.effective_message.reply_text(
            format_single_weather(report, forecast), parse_mode="Markdown"
        )
    else:
        await update.effective_message.reply_text(f"Không tìm thấy thời tiết cho '{city}'.")


@_safe_handler
async def disaster_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    alerts = await get_disaster_alerts()
    message = format_disaster_message(alerts)
    await update.effective_message.reply_text(
        message, parse_mode="Markdown", disable_web_page_preview=True
    )


@_safe_handler
async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    job_queue = context.job_queue
    if not job_queue:
        await update.effective_message.reply_text("Scheduler không khả dụng.")
        return

    existing_jobs = job_queue.get_jobs_by_name(f"disaster_{chat_id}")
    if existing_jobs:
        await update.effective_message.reply_text("Bạn đã đăng ký nhận cảnh báo rồi!")
        return

    disaster_interval = get_disaster_check_interval()

    job_queue.run_repeating(
        send_disaster_check,
        interval=disaster_interval * 60,
        first=30,
        chat_id=chat_id,
        name=f"disaster_{chat_id}",
    )

    await update.effective_message.reply_text(
        f"✅ Đã đăng ký nhận cảnh báo thiên tai!\n\n⚠️ Kiểm tra mỗi {disaster_interval} phút"
    )


@_safe_handler
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    await update.effective_message.reply_text(_build_help_text(), parse_mode="Markdown")


@_safe_handler
async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    job_queue = context.job_queue
    if not job_queue:
        return

    removed = 0
    for job in job_queue.get_jobs_by_name(f"disaster_{chat_id}"):
        job.schedule_removal()
        removed += 1

    if removed:
        await update.effective_message.reply_text("❌ Đã hủy đăng ký nhận cảnh báo thiên tai.")
    else:
        await update.effective_message.reply_text("Bạn chưa đăng ký nhận cảnh báo.")
