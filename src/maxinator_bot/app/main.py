from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from maxapi import Bot, Dispatcher

from maxinator_bot.app.bot.handlers import register_handlers
from maxinator_bot.app.config import get_settings
from maxinator_bot.app.database import Database
from maxinator_bot.app.services import ServiceContainer


def configure_logging() -> Path:
    log_path = Path("maxinator.log").resolve()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    return log_path


async def run_bot() -> None:
    log_path = configure_logging()
    logging.getLogger(__name__).info("Starting Maxinator; log file: %s", log_path)
    settings = get_settings()
    database = Database(settings)
    services = ServiceContainer.build(settings, database)
    dispatcher = Dispatcher()
    register_handlers(dispatcher, services)
    bot = Bot(token=settings.max_bot_token)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await database.dispose()


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
