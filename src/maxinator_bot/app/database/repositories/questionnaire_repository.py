from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from maxinator_bot.app.database.models import Question, Questionnaire


class QuestionnaireRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active_by_id(
        self,
        questionnaire_id: UUID,
    ) -> Questionnaire | None:
        statement = select(Questionnaire).where(
            Questionnaire.id == questionnaire_id,
            Questionnaire.is_active.is_(True),
        )
        return await self.session.scalar(statement)

    async def get_by_id(
        self,
        questionnaire_id: UUID,
    ) -> Questionnaire | None:
        return await self.session.get(Questionnaire, questionnaire_id)

    async def list_active(self) -> list[Questionnaire]:
        statement = (
            select(Questionnaire)
            .where(Questionnaire.is_active.is_(True))
            .order_by(Questionnaire.title, Questionnaire.version.desc())
        )
        return list((await self.session.scalars(statement)).all())

    async def list_active_questions(
        self,
        questionnaire_id: UUID,
    ) -> list[Question]:
        statement = (
            select(Question)
            .where(
                Question.questionnaire_id == questionnaire_id,
                Question.is_active.is_(True),
            )
            .order_by(Question.position)
        )
        return list((await self.session.scalars(statement)).all())
