from __future__ import annotations

import datetime as dt
import logging
import sys
from zoneinfo import ZoneInfo

from loguru import logger
from telegram import BotCommand
from telegram.ext import Application, ApplicationBuilder, CommandHandler

from vn_news_bot.adapters.llm import LLMClassifier
from vn_news_bot.config import (
    get_news_schedule,
    get_schedule_timezone,
    get_weather_digest_hour,
    get_weather_digest_minute,
    get_weather_monitor_interval,
    load_settings,
)
from vn_news_bot.handlers.commands import (
    disaster_command,
    economy_command,
    forecast_command,
    help_command,
    international_command,
    news_command,
    politics_command,
    search_command,
    sports_command,
    start_command,
    stock_command,
    subscribe_command,
    tech_command,
    trending_command,
    unsubscribe_command,
    weather_command,
)
from vn_news_bot.services.scheduler import (
    send_news_update,
    send_weather_digest,
    send_weather_monitor,
)


class _InterceptHandler(logging.Handler):
    """Route stdlib logging to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        frame = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _setup_logging(log_level: str) -> None:
    logger.remove()
    logger.add(sys.stderr, level=log_level.upper())

    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)


def _schedule_jobs(app: Application) -> None:
    job_queue = app.job_queue
    if not job_queue:
        logger.warning("Job queue not available, scheduled updates disabled")
        return

    tz = ZoneInfo(get_schedule_timezone())

    # News updates at fixed times
    for slot in get_news_schedule():
        job_queue.run_daily(
            send_news_update,
            time=dt.time(hour=slot["hour"], minute=slot["minute"], tzinfo=tz),
            name=f"news_{slot['hour']}:{slot['minute']:02d}",
        )
        logger.info("Scheduled news update at {}:{:02d}", slot["hour"], slot["minute"])

    # Weather digest daily
    digest_h = get_weather_digest_hour()
    digest_m = get_weather_digest_minute()
    job_queue.run_daily(
        send_weather_digest,
        time=dt.time(hour=digest_h, minute=digest_m, tzinfo=tz),
        name="weather_digest",
    )
    logger.info("Scheduled weather digest at {}:{:02d}", digest_h, digest_m)

    # Weather monitor repeating
    monitor_interval = get_weather_monitor_interval()
    job_queue.run_repeating(
        send_weather_monitor,
        interval=monitor_interval * 60,
        first=60,
        name="weather_monitor",
    )
    logger.info("Scheduled weather monitor every {} minutes", monitor_interval)


def main() -> None:
    settings = load_settings()
    _setup_logging(settings.log_level)

    async def post_init(application: Application) -> None:
        await application.bot.set_my_commands(
            [
                BotCommand("news", "Tin tức mới nhất"),
                BotCommand("trending", "Tin nổi bật"),
                BotCommand("thoisu", "Thời sự"),
                BotCommand("kinhte", "Kinh tế"),
                BotCommand("chungkhoan", "Chứng khoán"),
                BotCommand("quocte", "Quốc tế"),
                BotCommand("thethao", "Thể thao"),
                BotCommand("congnghe", "Công nghệ"),
                BotCommand("search", "Tìm tin theo từ khóa"),
                BotCommand("weather", "Thời tiết"),
                BotCommand("forecast", "Dự báo 7 ngày"),
                BotCommand("disaster", "Cảnh báo thiên tai"),
                BotCommand("subscribe", "Đăng ký cảnh báo"),
                BotCommand("unsubscribe", "Hủy đăng ký"),
                BotCommand("help", "Trợ giúp"),
            ]
        )

    app = ApplicationBuilder().token(settings.telegram_bot_token).post_init(post_init).build()

    app.bot_data["openweather_api_key"] = settings.openweather_api_key
    app.bot_data["newsapi_key"] = settings.newsapi_key
    app.bot_data["default_cities"] = settings.default_cities

    if settings.llm_api_key:
        app.bot_data["llm_classifier"] = LLMClassifier(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout=settings.llm_timeout,
        )
        logger.info("LLM classifier initialized (model={})", settings.llm_model)
    else:
        app.bot_data["llm_classifier"] = None
        logger.warning("LLM_API_KEY not set, using keyword fallback for disaster alerts")

    handlers = [
        ("start", start_command),
        ("news", news_command),
        ("trending", trending_command),
        ("thoisu", politics_command),
        ("kinhte", economy_command),
        ("chungkhoan", stock_command),
        ("quocte", international_command),
        ("thethao", sports_command),
        ("congnghe", tech_command),
        ("search", search_command),
        ("weather", weather_command),
        ("forecast", forecast_command),
        ("disaster", disaster_command),
        ("subscribe", subscribe_command),
        ("unsubscribe", unsubscribe_command),
        ("help", help_command),
    ]
    for cmd, handler in handlers:
        app.add_handler(CommandHandler(cmd, handler))

    _schedule_jobs(app)

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
