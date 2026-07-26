from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from maxinator_bot.app.database.models import TestAssignment


class AssignmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, assignment: TestAssignment) -> TestAssignment:
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def get_by_id(
        self,
        assignment_id: UUID,
        *,
        for_update: bool = False,
    ) -> TestAssignment | None:
        statement = select(TestAssignment).where(
            TestAssignment.id == assignment_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def get_by_access_code(
        self,
        access_code: str,
        *,
        for_update: bool = False,
    ) -> TestAssignment | None:
        statement = select(TestAssignment).where(
            TestAssignment.access_code == access_code,
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)
