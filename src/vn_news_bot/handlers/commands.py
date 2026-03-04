from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from vn_news_bot.adapters.telegram import (
    format_disaster_message,
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


async def sports_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    bot_data = context.bot_data or {}
    newsapi_key = bot_data.get("newsapi_key", "")

    scored = await get_latest_news(newsapi_key=newsapi_key, max_items=200)
    sports = [s for s in scored if s.category == "Thể thao"][:10]
    message = format_scored_news_message(sports) if sports else "Không có tin thể thao."
    await update.effective_message.reply_text(
        message, parse_mode="Markdown", disable_web_page_preview=True
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
        "*Danh sách lệnh:*\n\n"
        "/news - Tin tức nổi bật & mới nhất\n"
        "/thethao - Tin thể thao\n"
        "/weather - Thời tiết (mặc định: Hanoi)\n"
        "/weather <city> - Thời tiết thành phố\n"
        "/disaster - Cảnh báo thiên tai\n"
        "/subscribe - Đăng ký cảnh báo thiên tai\n"
        "/unsubscribe - Hủy đăng ký cảnh báo\n"
        "/help - Hiển thị trợ giúp\n\n"
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
