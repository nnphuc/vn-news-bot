from __future__ import annotations

import logging
import sys

from loguru import logger
from telegram.ext import ApplicationBuilder, CommandHandler

from vn_news_bot.config import load_settings
from vn_news_bot.handlers.commands import (
    disaster_command,
    help_command,
    news_command,
    start_command,
    subscribe_command,
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

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    app.bot_data["openweather_api_key"] = settings.openweather_api_key
    app.bot_data["newsapi_key"] = settings.newsapi_key
    app.bot_data["default_cities"] = settings.default_cities

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("disaster", disaster_command))
    app.add_handler(CommandHandler("subscribe", subscribe_command))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    app.add_handler(CommandHandler("help", help_command))

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
