from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from maxinator_bot.app.database.models import (
    AttemptAlert,
    AttemptCategoryResult,
    AttemptLieResult,
    Category,
    Question,
    TestAttempt,
)
from maxinator_bot.app.database.repositories import (
    AssignmentRepository,
    AttemptRepository,
    BotSessionRepository,
    ResultRepository,
)
from maxinator_bot.app.domain.enums import (
    AssignmentStatus,
    AttemptStatus,
    BotState,
    ScoringDirection,
)
from maxinator_bot.app.domain.constants import ANSWER_OPTIONS
from maxinator_bot.app.domain.models import (
    AttemptResultView,
    CompletedAttemptSummary,
)
from maxinator_bot.app.services.scoring_service import ScoringService


class ResultService:
    ALERT_TYPE = "requires_attention"

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        scoring_service: ScoringService,
    ) -> None:
        self.session_factory = session_factory
        self.scoring_service = scoring_service

    async def complete_attempt(
        self,
        session: AsyncSession,
        attempt: TestAttempt,
        max_user_id: str,
    ) -> bool:
        if attempt.status == AttemptStatus.COMPLETED:
            return True

        attempts = AttemptRepository(session)
        if await attempts.count_unanswered(attempt.id) != 0:
            return False

        results = ResultRepository(session)
        answer_rows = await results.list_answer_rows(attempt.id)
        grouped: dict[
            UUID,
            list[tuple[Question, Category, int]],
        ] = defaultdict(list)
        lie_answers: list[tuple[Question, int]] = []

        for attempt_question, question, category in answer_rows:
            if attempt_question.selected_value is None:
                return False
            if question.is_lie_question:
                lie_answers.append(
                    (question, attempt_question.selected_value),
                )
            else:
                grouped[category.id].append(
                    (
                        question,
                        category,
                        attempt_question.selected_value,
                    ),
                )

        for category_rows in grouped.values():
            await self._store_category_result(
                results,
                attempt.id,
                category_rows,
            )
        await self._store_lie_result(results, attempt.id, lie_answers)

        assignment = await AssignmentRepository(session).get_by_id(
            attempt.assignment_id,
            for_update=True,
        )
        if assignment is None:
            raise RuntimeError("Attempt assignment no longer exists")

        completed_at = datetime.now(timezone.utc)
        attempt.status = AttemptStatus.COMPLETED
        attempt.completed_at = completed_at
        assignment.status = AssignmentStatus.COMPLETED
        assignment.completed_at = completed_at
        await BotSessionRepository(session).update(
            max_user_id,
            state=BotState.IDLE,
            active_attempt_id=None,
            selected_patient_id=None,
            selected_questionnaire_id=None,
            page=None,
            context=None,
        )
        await session.flush()
        return True

    async def list_recent_completed(
        self,
        *,
        limit: int = 10,
    ) -> list[CompletedAttemptSummary]:
        async with self.session_factory() as session:
            return await ResultRepository(session).list_recent_completed(
                limit=limit,
            )

    async def list_patient_attempts(
        self,
        public_code: str,
    ) -> list[CompletedAttemptSummary]:
        async with self.session_factory() as session:
            return await ResultRepository(
                session,
            ).list_completed_for_patient_code(public_code)

    async def get_attempt_result(
        self,
        attempt_id: UUID,
    ) -> AttemptResultView | None:
        async with self.session_factory() as session:
            return await ResultRepository(session).get_result_view(
                attempt_id,
            )

    async def _store_category_result(
        self,
        repository: ResultRepository,
        attempt_id: UUID,
        rows: list[tuple[Question, Category, int]],
    ) -> None:
        question_directions = {
            question.scoring_direction
            for question, _category, _value in rows
        }
        if None in question_directions:
            return
        if not question_directions.issubset(
            {
                ScoringDirection.DIRECT,
                ScoringDirection.REVERSE,
                ScoringDirection.NONE,
            },
        ):
            return

        category = rows[0][1]
        existing = await repository.get_category_result(
            attempt_id,
            category.id,
        )
        if existing is None:
            scores = [
                self.scoring_service.score_question(question, value)
                for question, _category, value in rows
            ]
            if any(score is None for score in scores):
                return
            raw_score = sum(
                (score for score in scores if score is not None),
                Decimal("0"),
            )
            min_score = sum(
                (
                    question.weight
                    for question, _category, _value in rows
                    if question.scoring_direction
                    != ScoringDirection.NONE
                ),
                Decimal("0"),
            )
            max_score = sum(
                (
                    Decimal("5") * question.weight
                    for question, _category, _value in rows
                    if question.scoring_direction
                    != ScoringDirection.NONE
                ),
                Decimal("0"),
            )
            interpretation = await repository.get_interpretation(
                category.id,
                raw_score,
            )
            if interpretation is None:
                return

            existing = await repository.add_category_result(
                AttemptCategoryResult(
                    attempt_id=attempt_id,
                    category_id=category.id,
                    raw_score=raw_score,
                    min_possible_score=min_score,
                    max_possible_score=max_score,
                    level_code=interpretation.level_code,
                    level_title=interpretation.title,
                    interpretation=interpretation.description,
                ),
            )
        else:
            interpretation = await repository.get_interpretation(
                category.id,
                existing.raw_score,
            )

        if interpretation is None or not interpretation.requires_attention:
            return
        alert = await repository.get_alert(
            attempt_id,
            category.id,
            self.ALERT_TYPE,
        )
        if alert is None:
            await repository.add_alert(
                AttemptAlert(
                    attempt_id=attempt_id,
                    category_id=category.id,
                    alert_type=self.ALERT_TYPE,
                ),
            )

    async def _store_lie_result(
        self,
        repository: ResultRepository,
        attempt_id: UUID,
        lie_answers: list[tuple[Question, int]],
    ) -> None:
        if await repository.get_lie_result(attempt_id) is not None:
            return

        rules = await repository.list_lie_rules(
            [question.id for question, _value in lie_answers],
        )
        points_by_answer = {
            (rule.question_id, rule.answer_value): rule.points
            for rule in rules
        }
        expected_rules = {
            (question.id, answer_value)
            for question, _selected_value in lie_answers
            for answer_value in ANSWER_OPTIONS
        }
        scoring_configured = bool(lie_answers) and expected_rules.issubset(
            points_by_answer,
        )

        if not scoring_configured:
            await repository.add_lie_result(
                AttemptLieResult(
                    attempt_id=attempt_id,
                    score=None,
                    level_code=None,
                    interpretation=None,
                    scoring_configured=False,
                ),
            )
            return

        score = sum(
            points_by_answer[(question.id, selected_value)]
            for question, selected_value in lie_answers
        )
        level_code, interpretation = (
            self.scoring_service.interpret_lie_score(score)
        )
        await repository.add_lie_result(
            AttemptLieResult(
                attempt_id=attempt_id,
                score=score,
                level_code=level_code,
                interpretation=interpretation,
                scoring_configured=True,
            ),
        )
