from __future__ import annotations

import secrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from maxinator_bot.app.config import Settings
from maxinator_bot.app.database.models import (
    AttemptQuestion,
    TestAssignment,
    TestAttempt,
)
from maxinator_bot.app.database.repositories import (
    AssignmentRepository,
    AttemptRepository,
    BotSessionRepository,
    PatientRepository,
    QuestionnaireRepository,
)
from maxinator_bot.app.domain.enums import (
    AssignmentStatus,
    AttemptStatus,
    BotState,
)
from maxinator_bot.app.domain.models import AnswerOutcome, QuestionProgress
from maxinator_bot.app.services.code_generator import CodeGenerator
from maxinator_bot.app.services.scoring_service import ScoringService
from maxinator_bot.app.services.result_service import ResultService


class AssignmentAccessDeniedError(RuntimeError):
    pass


class AttemptAnswerDeniedError(RuntimeError):
    pass


class EmptyQuestionnaireError(RuntimeError):
    pass


class AttemptService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        code_generator: CodeGenerator,
        scoring_service: ScoringService,
        result_service: ResultService,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.code_generator = code_generator
        self.scoring_service = scoring_service
        self.result_service = result_service

    async def start_or_resume(
        self,
        access_code: str,
        max_user_id: str,
    ) -> QuestionProgress:
        normalized_code = "".join(access_code.split())
        if not self.code_generator.is_valid(
            normalized_code,
            self.settings.assignment_code_length,
        ):
            raise AssignmentAccessDeniedError

        denied = False
        progress: QuestionProgress | None = None
        async with self.session_factory() as session:
            async with session.begin():
                assignments = AssignmentRepository(session)
                attempts = AttemptRepository(session)
                assignment = await assignments.get_by_access_code(
                    normalized_code,
                    for_update=True,
                )
                if assignment is None:
                    denied = True
                elif self._is_expired(assignment.expires_at):
                    if assignment.status not in {
                        AssignmentStatus.COMPLETED,
                        AssignmentStatus.CANCELLED,
                    }:
                        assignment.status = AssignmentStatus.EXPIRED
                    denied = True
                elif assignment.status not in {
                    AssignmentStatus.CREATED,
                    AssignmentStatus.IN_PROGRESS,
                }:
                    denied = True
                else:
                    patient = await PatientRepository(session).get_by_id(
                        assignment.patient_id,
                        for_update=True,
                    )
                    if patient is None:
                        denied = True
                    elif (
                        patient.max_user_id is not None
                        and patient.max_user_id != max_user_id
                    ):
                        denied = True
                    else:
                        if patient.max_user_id is None:
                            patient.max_user_id = max_user_id

                        attempt = await attempts.get_by_assignment_id(
                            assignment.id,
                            for_update=True,
                        )
                        if attempt is None:
                            attempt = await self._create_attempt(
                                session,
                                assignment,
                            )
                        elif attempt.status != AttemptStatus.IN_PROGRESS:
                            denied = True

                        if not denied:
                            assignment.status = AssignmentStatus.IN_PROGRESS
                            if assignment.started_at is None:
                                assignment.started_at = datetime.now(
                                    timezone.utc,
                                )
                            await BotSessionRepository(session).update(
                                max_user_id,
                                state=BotState.TAKING_QUESTIONNAIRE,
                                selected_patient_id=assignment.patient_id,
                                selected_questionnaire_id=(
                                    assignment.questionnaire_id
                                ),
                                active_attempt_id=attempt.id,
                                page=None,
                                context=None,
                            )
                            progress = await attempts.get_current_question(
                                attempt.id,
                                max_user_id,
                            )

        if denied or progress is None:
            raise AssignmentAccessDeniedError
        return progress

    async def resume_active(
        self,
        attempt_id: UUID,
        max_user_id: str,
    ) -> QuestionProgress | None:
        async with self.session_factory() as session:
            return await AttemptRepository(session).get_current_question(
                attempt_id,
                max_user_id,
            )

    async def answer_question(
        self,
        attempt_question_id: UUID,
        selected_value: int,
        max_user_id: str,
    ) -> AnswerOutcome:
        self.scoring_service.validate_answer(selected_value)

        async with self.session_factory() as session:
            async with session.begin():
                attempts = AttemptRepository(session)
                locked = await attempts.lock_attempt_question(
                    attempt_question_id,
                )
                if locked is None:
                    raise AttemptAnswerDeniedError
                attempt_question, attempt, patient, question = locked

                if patient.max_user_id != max_user_id:
                    raise AttemptAnswerDeniedError

                if attempt_question.selected_value is not None:
                    next_question = await attempts.get_current_question(
                        attempt.id,
                        max_user_id,
                    )
                    return AnswerOutcome(
                        attempt_id=attempt.id,
                        next_question=next_question,
                        completed=(
                            attempt.status == AttemptStatus.COMPLETED
                        ),
                        duplicate=True,
                    )

                if attempt.status != AttemptStatus.IN_PROGRESS:
                    raise AttemptAnswerDeniedError

                current = await attempts.get_current_question(
                    attempt.id,
                    max_user_id,
                )
                if (
                    current is None
                    or current.attempt_question_id != attempt_question.id
                ):
                    raise AttemptAnswerDeniedError

                attempt_question.selected_value = selected_value
                attempt_question.calculated_category_score = (
                    self.scoring_service.score_question(
                        question,
                        selected_value,
                    )
                )
                attempt_question.answered_at = datetime.now(timezone.utc)
                attempt.current_question_index = (
                    attempt_question.order_index + 1
                )
                await session.flush()

                next_question = await attempts.get_current_question(
                    attempt.id,
                    max_user_id,
                )
                if next_question is not None:
                    return AnswerOutcome(
                        attempt_id=attempt.id,
                        next_question=next_question,
                        completed=False,
                        duplicate=False,
                    )

                completed = await self.result_service.complete_attempt(
                    session,
                    attempt,
                    max_user_id,
                )
                return AnswerOutcome(
                    attempt_id=attempt.id,
                    next_question=None,
                    completed=completed,
                    duplicate=False,
                )

    async def _create_attempt(
        self,
        session: AsyncSession,
        assignment: TestAssignment,
    ) -> TestAttempt:
        questionnaires = QuestionnaireRepository(session)
        questionnaire = await questionnaires.get_by_id(
            assignment.questionnaire_id,
        )
        if questionnaire is None:
            raise AssignmentAccessDeniedError

        questions = await questionnaires.list_active_questions(
            questionnaire.id,
        )
        if not questions:
            raise EmptyQuestionnaireError

        secrets.SystemRandom().shuffle(questions)
        attempt = TestAttempt(
            assignment_id=assignment.id,
            patient_id=assignment.patient_id,
            questionnaire_id=questionnaire.id,
            questionnaire_version=questionnaire.version,
        )
        repository = AttemptRepository(session)
        await repository.add(attempt)
        await repository.add_attempt_questions(
            [
                AttemptQuestion(
                    attempt_id=attempt.id,
                    question_id=question.id,
                    order_index=order_index,
                )
                for order_index, question in enumerate(questions)
            ],
        )
        return attempt

    @staticmethod
    def _is_expired(expires_at: datetime | None) -> bool:
        return (
            expires_at is not None
            and expires_at <= datetime.now(timezone.utc)
        )
