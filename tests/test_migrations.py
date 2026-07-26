from __future__ import annotations

import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from maxinator_bot.app.config import get_settings


async def list_tables(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            return set(
                await connection.run_sync(
                    lambda sync_connection: inspect(
                        sync_connection,
                    ).get_table_names(),
                ),
            )
    finally:
        await engine.dispose()


def test_initial_migration_upgrades_and_downgrades(
    postgres_url: str,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MAX_BOT_TOKEN", "test")
    monkeypatch.setenv("DATABASE_URL", postgres_url)
    monkeypatch.setenv("ADMIN_MAX_IDS", "")
    get_settings.cache_clear()

    config = Config("alembic.ini")
    command.upgrade(config, "head")
    upgraded_tables = asyncio.run(list_tables(postgres_url))

    assert "patients" in upgraded_tables
    assert "attempt_questions" in upgraded_tables
    assert "bot_sessions" in upgraded_tables

    command.downgrade(config, "base")
    downgraded_tables = asyncio.run(list_tables(postgres_url))
    get_settings.cache_clear()

    assert "patients" not in downgraded_tables
    assert "attempt_questions" not in downgraded_tables
    assert "bot_sessions" not in downgraded_tables
