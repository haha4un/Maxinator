from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.community.postgres import PostgresContainer

from maxinator_bot.app.database.base import Base
from maxinator_bot.app.database import models  # noqa: F401


def to_asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if "postgresql+psycopg2://" in url:
        return url.replace(
            "postgresql+psycopg2://",
            "postgresql+asyncpg://",
            1,
        )
    return url.replace(
        "postgresql://",
        "postgresql+asyncpg://",
        1,
    )


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    configured_url = os.getenv("TEST_DATABASE_URL")
    if configured_url:
        yield to_asyncpg_url(configured_url)
        return

    try:
        container = PostgresContainer("postgres:17")
        container.start()
    except Exception as exc:
        pytest.skip(f"PostgreSQL test container is unavailable: {exc}")

    try:
        yield to_asyncpg_url(container.get_connection_url())
    finally:
        container.stop()


@pytest_asyncio.fixture
async def session_factory(
    postgres_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(postgres_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    try:
        yield factory
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()
