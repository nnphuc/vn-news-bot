from __future__ import annotations

import re
import unicodedata

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


def _build_welcome_message() -> str:
    cities = get_cities()
    return (
        "🇻🇳 *Chào mừng bạn đến với VN News Bot!*\n\n"
        "Bot cung cấp tin tức, thời tiết và cảnh báo thiên tai cho Việt Nam.\n\n"
        "*Các lệnh:*\n"
        "/news - Tin tức mới nhất\n"
        "/weather <thành phố> - Thời tiết (VD: /weather Hanoi)\n"
        "/disaster - Cảnh báo thiên tai\n"
        "/subscribe - Đăng ký cảnh báo thiên tai\n"
        "/unsubscribe - Hủy đăng ký cảnh báo\n"
        "/help - Trợ giúp\n\n"
        f"*Thành phố hỗ trợ:* {', '.join(cities.keys())}"
    )


def _resolve_city(name: str) -> str | None:
    cities = get_cities()
    if name in cities:
        return name
    return get_city_aliases().get(name.lower().strip())


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    await update.effective_message.reply_text(_build_welcome_message(), parse_mode="Markdown")


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    bot_data = context.bot_data or {}
    newsapi_key = bot_data.get("newsapi_key", "")

    scored = await get_latest_news(newsapi_key=newsapi_key)
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

    bot_data = context.bot_data or {}
    newsapi_key = bot_data.get("newsapi_key", "")

    scored = await get_latest_news(newsapi_key=newsapi_key, max_items=200)
    cat_set = set(categories)
    filtered = [s for s in scored if s.category in cat_set][:10]
    message = format_scored_news_message(filtered) if filtered else empty_msg
    await update.effective_message.reply_text(
        message, parse_mode="Markdown", disable_web_page_preview=True
    )


async def sports_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _category_command(update, context, ["Thể thao"], "Không có tin thể thao.")


async def economy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _category_command(
        update, context, ["Kinh tế", "Chứng khoán"], "Không có tin kinh tế."
    )


async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _category_command(update, context, ["Chứng khoán"], "Không có tin chứng khoán.")


async def international_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _category_command(update, context, ["Quốc tế"], "Không có tin quốc tế.")


async def politics_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _category_command(
        update, context, ["Thời sự", "Pháp luật"], "Không có tin thời sự."
    )


async def tech_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _category_command(update, context, ["Công nghệ"], "Không có tin công nghệ.")


async def trending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    bot_data = context.bot_data or {}
    newsapi_key = bot_data.get("newsapi_key", "")

    scored = await get_latest_news(newsapi_key=newsapi_key, max_items=200)
    hot = [s for s in scored if s.is_trending][:10]
    message = format_scored_news_message(hot) if hot else "Không có tin nổi bật."
    await update.effective_message.reply_text(
        message, parse_mode="Markdown", disable_web_page_preview=True
    )


def _strip_accents(text: str) -> str:
    text = text.replace("Đ", "D").replace("đ", "d")
    nfkd = unicodedata.normalize("NFKD", text)
    return re.sub(r"[\u0300-\u036f\u0301\u0303\u0309\u0323]", "", nfkd).lower()


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    if not context.args:
        await update.effective_message.reply_text("Dùng: /search <từ khóa>")
        return

    keyword = " ".join(context.args).lower()
    keyword_no_accent = _strip_accents(keyword)
    bot_data = context.bot_data or {}
    newsapi_key = bot_data.get("newsapi_key", "")

    scored = await get_latest_news(newsapi_key=newsapi_key, max_items=200)
    results = [
        s for s in scored
        if keyword in s.article.title.lower()
        or keyword_no_accent in _strip_accents(s.article.title)
    ][:10]
    if results:
        message = format_scored_news_message(results)
    else:
        message = f"Không tìm thấy tin về '{keyword}'."
    await update.effective_message.reply_text(
        message, parse_mode="Markdown", disable_web_page_preview=True
    )


async def forecast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    city_input = "Hanoi" if not context.args else " ".join(context.args)
    city = _resolve_city(city_input) or city_input

    forecast = await get_forecast_for_city(city)
    if forecast:
        await update.effective_message.reply_text(
            format_forecast_message(city, forecast), parse_mode="Markdown"
        )
    else:
        cities = get_cities()
        await update.effective_message.reply_text(
            f"Không tìm thấy dự báo cho '{city_input}'.\n"
            f"Thành phố có sẵn: {', '.join(cities.keys())}"
        )


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    city_input = "Hanoi" if not context.args else " ".join(context.args)
    city = _resolve_city(city_input) or city_input

    bot_data = context.bot_data or {}
    api_key = bot_data.get("openweather_api_key", "")
    report = await get_weather_for_city(city, api_key)

    if report:
        forecast = await get_forecast_for_city(city)
        await update.effective_message.reply_text(
            format_single_weather(report, forecast), parse_mode="Markdown"
        )
    else:
        cities = get_cities()
        await update.effective_message.reply_text(
            f"Không tìm thấy thời tiết cho '{city_input}'.\n"
            f"Thành phố có sẵn: {', '.join(cities.keys())}"
        )


async def disaster_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    alerts = await get_disaster_alerts()
    message = format_disaster_message(alerts)
    await update.effective_message.reply_text(
        message, parse_mode="Markdown", disable_web_page_preview=True
    )


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
        "✅ Đã đăng ký nhận cảnh báo thiên tai!\n\n"
        f"⚠️ Kiểm tra mỗi {disaster_interval} phút"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    cities = get_cities()
    message = (
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
    await update.effective_message.reply_text(message, parse_mode="Markdown")


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
