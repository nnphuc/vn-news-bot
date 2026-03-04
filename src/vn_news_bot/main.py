from __future__ import annotations

import logging
import sys

from loguru import logger
from telegram import BotCommand
from telegram.ext import Application, ApplicationBuilder, CommandHandler

from vn_news_bot.config import load_settings
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


def main() -> None:
    settings = load_settings()
    _setup_logging(settings.log_level)

    async def post_init(application: Application) -> None:
        await application.bot.set_my_commands([
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
        ])

    app = ApplicationBuilder().token(settings.telegram_bot_token).post_init(post_init).build()

    app.bot_data["openweather_api_key"] = settings.openweather_api_key
    app.bot_data["newsapi_key"] = settings.newsapi_key
    app.bot_data["default_cities"] = settings.default_cities

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

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
