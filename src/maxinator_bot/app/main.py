from __future__ import annotations

import asyncio

from maxapi import Bot, Dispatcher

from maxinator_bot.app.bot.handlers import register_handlers
from maxinator_bot.app.config import get_settings
from maxinator_bot.app.database import Database
from maxinator_bot.app.services import ServiceContainer


async def run_bot() -> None:
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
