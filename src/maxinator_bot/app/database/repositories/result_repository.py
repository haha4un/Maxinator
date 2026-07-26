from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from maxinator_bot.app.database.models import (
    AttemptAlert,
    AttemptCategoryResult,
    AttemptLieResult,
    AttemptQuestion,
    Category,
    CategoryInterpretationRange,
    LieQuestionAnswerScore,
    Patient,
    Question,
    Questionnaire,
    TestAssignment,
    TestAttempt,
)
from maxinator_bot.app.domain.enums import AttemptStatus
from maxinator_bot.app.domain.models import (
    AttemptResultView,
    CategoryResultView,
    CompletedAttemptSummary,
    LieResultView,
)


class ResultRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_answer_rows(
        self,
        attempt_id: UUID,
    ) -> list[tuple[AttemptQuestion, Question, Category]]:
        statement = (
            select(AttemptQuestion, Question, Category)
            .join(Question, Question.id == AttemptQuestion.question_id)
            .join(Category, Category.id == Question.category_id)
            .where(AttemptQuestion.attempt_id == attempt_id)
            .order_by(Category.position, AttemptQuestion.order_index)
        )
        rows = (await self.session.execute(statement)).all()
        return [row.tuple() for row in rows]

    async def get_interpretation(
        self,
        category_id: UUID,
        score: Decimal,
    ) -> CategoryInterpretationRange | None:
        statement = select(CategoryInterpretationRange).where(
            CategoryInterpretationRange.category_id == category_id,
            CategoryInterpretationRange.min_score <= score,
            CategoryInterpretationRange.max_score >= score,
        )
        return await self.session.scalar(statement)

    async def get_category_result(
        self,
        attempt_id: UUID,
        category_id: UUID,
    ) -> AttemptCategoryResult | None:
        statement = select(AttemptCategoryResult).where(
            AttemptCategoryResult.attempt_id == attempt_id,
            AttemptCategoryResult.category_id == category_id,
        )
        return await self.session.scalar(statement)

    async def add_category_result(
        self,
        result: AttemptCategoryResult,
    ) -> AttemptCategoryResult:
        self.session.add(result)
        await self.session.flush()
        return result

    async def list_lie_rules(
        self,
        question_ids: Sequence[UUID],
    ) -> list[LieQuestionAnswerScore]:
        if not question_ids:
            return []
        statement = select(LieQuestionAnswerScore).where(
            LieQuestionAnswerScore.question_id.in_(question_ids),
        )
        return list((await self.session.scalars(statement)).all())

    async def get_lie_result(
        self,
        attempt_id: UUID,
    ) -> AttemptLieResult | None:
        statement = select(AttemptLieResult).where(
            AttemptLieResult.attempt_id == attempt_id,
        )
        return await self.session.scalar(statement)

    async def add_lie_result(
        self,
        result: AttemptLieResult,
    ) -> AttemptLieResult:
        self.session.add(result)
        await self.session.flush()
        return result

    async def get_alert(
        self,
        attempt_id: UUID,
        category_id: UUID,
        alert_type: str,
    ) -> AttemptAlert | None:
        statement = select(AttemptAlert).where(
            AttemptAlert.attempt_id == attempt_id,
            AttemptAlert.category_id == category_id,
            AttemptAlert.alert_type == alert_type,
        )
        return await self.session.scalar(statement)

    async def add_alert(self, alert: AttemptAlert) -> AttemptAlert:
        self.session.add(alert)
        await self.session.flush()
        return alert

    async def list_recent_completed(
        self,
        *,
        limit: int = 10,
    ) -> list[CompletedAttemptSummary]:
        statement = (
            select(
                TestAttempt.id,
                Patient.public_code,
                Questionnaire.title,
                TestAttempt.completed_at,
            )
            .join(
                TestAssignment,
                TestAssignment.id == TestAttempt.assignment_id,
            )
            .join(Patient, Patient.id == TestAttempt.patient_id)
            .join(
                Questionnaire,
                Questionnaire.id == TestAttempt.questionnaire_id,
            )
            .where(
                TestAttempt.status == AttemptStatus.COMPLETED,
                TestAttempt.completed_at.is_not(None),
            )
            .order_by(TestAttempt.completed_at.desc())
            .limit(limit)
        )
        rows = (await self.session.execute(statement)).all()
        return [
            CompletedAttemptSummary(
                attempt_id=row.id,
                patient_code=row.public_code,
                questionnaire_title=row.title,
                completed_at=row.completed_at,
            )
            for row in rows
        ]

    async def list_completed_for_patient_code(
        self,
        public_code: str,
    ) -> list[CompletedAttemptSummary]:
        statement = (
            select(
                TestAttempt.id,
                Patient.public_code,
                Questionnaire.title,
                TestAttempt.completed_at,
            )
            .join(Patient, Patient.id == TestAttempt.patient_id)
            .join(
                Questionnaire,
                Questionnaire.id == TestAttempt.questionnaire_id,
            )
            .where(
                Patient.public_code == public_code,
                TestAttempt.status == AttemptStatus.COMPLETED,
                TestAttempt.completed_at.is_not(None),
            )
            .order_by(TestAttempt.completed_at.desc())
        )
        rows = (await self.session.execute(statement)).all()
        return [
            CompletedAttemptSummary(
                attempt_id=row.id,
                patient_code=row.public_code,
                questionnaire_title=row.title,
                completed_at=row.completed_at,
            )
            for row in rows
        ]

    async def get_result_view(
        self,
        attempt_id: UUID,
    ) -> AttemptResultView | None:
        main_statement = (
            select(
                TestAttempt.id,
                Patient.public_code,
                Questionnaire.title,
                TestAssignment.created_at.label("assigned_at"),
                TestAttempt.started_at,
                TestAttempt.completed_at,
            )
            .join(
                TestAssignment,
                TestAssignment.id == TestAttempt.assignment_id,
            )
            .join(Patient, Patient.id == TestAttempt.patient_id)
            .join(
                Questionnaire,
                Questionnaire.id == TestAttempt.questionnaire_id,
            )
            .where(
                TestAttempt.id == attempt_id,
                TestAttempt.status == AttemptStatus.COMPLETED,
                TestAttempt.completed_at.is_not(None),
            )
        )
        main = (await self.session.execute(main_statement)).one_or_none()
        if main is None:
            return None

        category_statement = (
            select(
                AttemptCategoryResult,
                Category,
                AttemptAlert.id.label("alert_id"),
            )
            .join(
                Category,
                Category.id == AttemptCategoryResult.category_id,
            )
            .outerjoin(
                AttemptAlert,
                and_(
                    AttemptAlert.attempt_id
                    == AttemptCategoryResult.attempt_id,
                    AttemptAlert.category_id
                    == AttemptCategoryResult.category_id,
                    AttemptAlert.alert_type == "requires_attention",
                ),
            )
            .where(AttemptCategoryResult.attempt_id == attempt_id)
            .order_by(Category.position)
        )
        category_rows = (
            await self.session.execute(category_statement)
        ).all()
        categories = [
            CategoryResultView(
                category_name=row.Category.name,
                raw_score=row.AttemptCategoryResult.raw_score,
                level_title=row.AttemptCategoryResult.level_title,
                interpretation=row.AttemptCategoryResult.interpretation,
                requires_attention=row.alert_id is not None,
            )
            for row in category_rows
        ]

        lie_result = await self.get_lie_result(attempt_id)
        lie_view = LieResultView(
            score=None if lie_result is None else lie_result.score,
            level_code=(
                None if lie_result is None else lie_result.level_code
            ),
            interpretation=(
                None if lie_result is None else lie_result.interpretation
            ),
            scoring_configured=(
                False
                if lie_result is None
                else lie_result.scoring_configured
            ),
        )
        return AttemptResultView(
            attempt_id=main.id,
            patient_code=main.public_code,
            questionnaire_title=main.title,
            assigned_at=main.assigned_at,
            started_at=main.started_at,
            completed_at=main.completed_at,
            categories=categories,
            lie_result=lie_view,
        )

    async def lock_pending_alert_rows(
        self,
        attempt_id: UUID,
    ) -> list[tuple[AttemptAlert, str, str, str, str]]:
        statement = (
            select(
                AttemptAlert,
                Patient.public_code,
                Questionnaire.title,
                Category.name,
                AttemptCategoryResult.level_title,
            )
            .join(
                TestAttempt,
                TestAttempt.id == AttemptAlert.attempt_id,
            )
            .join(Patient, Patient.id == TestAttempt.patient_id)
            .join(
                Questionnaire,
                Questionnaire.id == TestAttempt.questionnaire_id,
            )
            .join(Category, Category.id == AttemptAlert.category_id)
            .join(
                AttemptCategoryResult,
                and_(
                    AttemptCategoryResult.attempt_id
                    == AttemptAlert.attempt_id,
                    AttemptCategoryResult.category_id
                    == AttemptAlert.category_id,
                ),
            )
            .where(
                AttemptAlert.attempt_id == attempt_id,
                AttemptAlert.notified_at.is_(None),
            )
            .with_for_update(of=AttemptAlert)
        )
        rows = (await self.session.execute(statement)).all()
        return [
            (
                row.AttemptAlert,
                row.public_code,
                row.title,
                row.name,
                row.level_title,
            )
            for row in rows
        ]
