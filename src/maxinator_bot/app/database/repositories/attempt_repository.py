from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from maxinator_bot.app.database.models import (
    AttemptQuestion,
    Patient,
    Question,
    TestAttempt,
)
from maxinator_bot.app.domain.enums import AttemptStatus
from maxinator_bot.app.domain.models import QuestionProgress


class AttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, attempt: TestAttempt) -> TestAttempt:
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def get_by_assignment_id(
        self,
        assignment_id: UUID,
        *,
        for_update: bool = False,
    ) -> TestAttempt | None:
        statement = select(TestAttempt).where(
            TestAttempt.assignment_id == assignment_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def get_by_id(
        self,
        attempt_id: UUID,
        *,
        for_update: bool = False,
    ) -> TestAttempt | None:
        statement = select(TestAttempt).where(TestAttempt.id == attempt_id)
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def add_attempt_questions(
        self,
        attempt_questions: list[AttemptQuestion],
    ) -> None:
        self.session.add_all(attempt_questions)
        await self.session.flush()

    async def get_current_question(
        self,
        attempt_id: UUID,
        max_user_id: str,
    ) -> QuestionProgress | None:
        total_subquery = (
            select(func.count(AttemptQuestion.id))
            .where(AttemptQuestion.attempt_id == attempt_id)
            .scalar_subquery()
        )
        statement = (
            select(
                AttemptQuestion.id,
                AttemptQuestion.attempt_id,
                AttemptQuestion.order_index,
                Question.text,
                total_subquery.label("total"),
            )
            .join(
                TestAttempt,
                TestAttempt.id == AttemptQuestion.attempt_id,
            )
            .join(Patient, Patient.id == TestAttempt.patient_id)
            .join(Question, Question.id == AttemptQuestion.question_id)
            .where(
                AttemptQuestion.attempt_id == attempt_id,
                AttemptQuestion.selected_value.is_(None),
                TestAttempt.status == AttemptStatus.IN_PROGRESS,
                Patient.max_user_id == max_user_id,
            )
            .order_by(AttemptQuestion.order_index)
            .limit(1)
        )
        row = (await self.session.execute(statement)).one_or_none()
        if row is None:
            return None
        return QuestionProgress(
            attempt_id=row.attempt_id,
            attempt_question_id=row.id,
            question_text=row.text,
            current_number=row.order_index + 1,
            total=row.total,
        )

    async def lock_attempt_question(
        self,
        attempt_question_id: UUID,
    ) -> tuple[AttemptQuestion, TestAttempt, Patient, Question] | None:
        statement = (
            select(AttemptQuestion, TestAttempt, Patient, Question)
            .join(
                TestAttempt,
                TestAttempt.id == AttemptQuestion.attempt_id,
            )
            .join(Patient, Patient.id == TestAttempt.patient_id)
            .join(Question, Question.id == AttemptQuestion.question_id)
            .where(AttemptQuestion.id == attempt_question_id)
            .with_for_update(of=(AttemptQuestion, TestAttempt))
        )
        row = (await self.session.execute(statement)).one_or_none()
        if row is None:
            return None
        return row.tuple()

    async def count_unanswered(self, attempt_id: UUID) -> int:
        statement = select(func.count(AttemptQuestion.id)).where(
            AttemptQuestion.attempt_id == attempt_id,
            AttemptQuestion.selected_value.is_(None),
        )
        return int(await self.session.scalar(statement) or 0)
