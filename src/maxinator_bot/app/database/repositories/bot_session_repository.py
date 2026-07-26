from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from maxinator_bot.app.database.models import BotSession
from maxinator_bot.app.domain.enums import BotState


class BotSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self, max_user_id: str) -> BotSession:
        statement = (
            insert(BotSession)
            .values(max_user_id=max_user_id, state=BotState.IDLE)
            .on_conflict_do_nothing(index_elements=[BotSession.max_user_id])
        )
        await self.session.execute(statement)
        bot_session = await self.session.scalar(
            select(BotSession).where(
                BotSession.max_user_id == max_user_id,
            ),
        )
        if bot_session is None:
            raise RuntimeError("Unable to create bot session")
        return bot_session

    async def update(
        self,
        max_user_id: str,
        **values: Any,
    ) -> BotSession:
        await self.get_or_create(max_user_id)
        await self.session.execute(
            update(BotSession)
            .where(BotSession.max_user_id == max_user_id)
            .values(**values),
        )
        bot_session = await self.session.get(BotSession, max_user_id)
        if bot_session is None:
            raise RuntimeError("Bot session disappeared during update")
        await self.session.refresh(bot_session)
        return bot_session
