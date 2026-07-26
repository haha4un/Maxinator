from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from maxinator_bot.app.config import Settings
from maxinator_bot.app.database.models import (
    AttemptCategoryResult,
    AttemptLieResult,
    AttemptQuestion,
    Category,
    CategoryInterpretationRange,
    LieQuestionAnswerScore,
    Patient,
    Question,
    Questionnaire,
    TestAssignment as DbTestAssignment,
    TestAttempt as DbTestAttempt,
)
from maxinator_bot.app.domain.enums import (
    AssignmentStatus,
    ScoringDirection,
)
from maxinator_bot.app.services.attempt_service import (
    AssignmentAccessDeniedError,
    AttemptService,
)
from maxinator_bot.app.services.code_generator import CodeGenerator
from maxinator_bot.app.services.result_service import ResultService
from maxinator_bot.app.services.scoring_service import ScoringService
from maxinator_bot.app.seed.questionnaire_seed import seed_questionnaire


@dataclass(frozen=True, slots=True)
class FlowData:
    patient_id: UUID
    questionnaire_id: UUID
    assignment_id: UUID
    access_code: str
    question_ids: list[UUID]


def build_services(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[AttemptService, ResultService]:
    settings = Settings(
        max_bot_token="test",
        database_url=(
            "postgresql+asyncpg://postgres:postgres@localhost/test"
        ),
        admin_max_ids=set(),
        _env_file=None,
    )
    scoring = ScoringService()
    results = ResultService(factory, scoring)
    attempts = AttemptService(
        factory,
        settings,
        CodeGenerator(),
        scoring,
        results,
    )
    return attempts, results


async def create_flow(
    factory: async_sessionmaker[AsyncSession],
    *,
    access_code: str = "12345678",
    patient_code: str = "123456",
    patient_max_user_id: str | None = None,
    question_count: int = 2,
    lie_positions: set[int] | None = None,
) -> FlowData:
    lie_positions = lie_positions or set()
    async with factory() as session:
        async with session.begin():
            patient = Patient(
                public_code=patient_code,
                max_user_id=patient_max_user_id,
            )
            questionnaire = Questionnaire(
                code=f"test_{access_code}",
                title="Тестовый опросник",
                version=1,
                is_active=True,
            )
            session.add_all([patient, questionnaire])
            await session.flush()

            category = Category(
                questionnaire_id=questionnaire.id,
                code="category",
                name="Категория",
                position=1,
            )
            session.add(category)
            await session.flush()
            session.add(
                CategoryInterpretationRange(
                    category_id=category.id,
                    min_score=Decimal("1"),
                    max_score=Decimal(5 * question_count),
                    level_code="configured",
                    title="Настроено",
                    description="Тестовая интерпретация",
                    requires_attention=False,
                ),
            )

            questions = []
            for position in range(1, question_count + 1):
                is_lie = position in lie_positions
                questions.append(
                    Question(
                        questionnaire_id=questionnaire.id,
                        category_id=category.id,
                        text=f"Вопрос {position}",
                        position=position,
                        weight=(
                            Decimal("0")
                            if is_lie
                            else Decimal("1")
                        ),
                        scoring_direction=(
                            ScoringDirection.NONE
                            if is_lie
                            else ScoringDirection.DIRECT
                        ),
                        is_lie_question=is_lie,
                        is_active=True,
                    ),
                )
            session.add_all(questions)
            await session.flush()

            assignment = DbTestAssignment(
                patient_id=patient.id,
                questionnaire_id=questionnaire.id,
                access_code=access_code,
                created_by_admin_max_user_id="999",
            )
            session.add(assignment)
            await session.flush()

            return FlowData(
                patient_id=patient.id,
                questionnaire_id=questionnaire.id,
                assignment_id=assignment.id,
                access_code=assignment.access_code,
                question_ids=[question.id for question in questions],
            )


async def answer_until_complete(
    attempts: AttemptService,
    access_code: str,
    max_user_id: str,
    *,
    value: int = 3,
) -> UUID:
    progress = await attempts.start_or_resume(access_code, max_user_id)
    while True:
        outcome = await attempts.answer_question(
            progress.attempt_question_id,
            value,
            max_user_id,
        )
        if outcome.completed:
            return outcome.attempt_id
        assert outcome.next_question is not None
        progress = outcome.next_question


@pytest.mark.asyncio
async def test_lie_answer_is_saved(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    flow = await create_flow(
        session_factory,
        question_count=1,
        lie_positions={1},
    )
    attempts, _results = build_services(session_factory)
    progress = await attempts.start_or_resume(flow.access_code, "100")

    outcome = await attempts.answer_question(
        progress.attempt_question_id,
        5,
        "100",
    )

    assert outcome.completed is True
    async with session_factory() as session:
        saved_value = await session.scalar(
            select(AttemptQuestion.selected_value).where(
                AttemptQuestion.id == progress.attempt_question_id,
            ),
        )
    assert saved_value == 5


@pytest.mark.asyncio
async def test_random_question_order_is_persisted(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    flow = await create_flow(session_factory, question_count=12)
    attempts, _results = build_services(session_factory)
    progress = await attempts.start_or_resume(flow.access_code, "100")

    async with session_factory() as session:
        first_order = list(
            (
                await session.scalars(
                    select(Question.position)
                    .join(
                        AttemptQuestion,
                        AttemptQuestion.question_id == Question.id,
                    )
                    .where(
                        AttemptQuestion.attempt_id == progress.attempt_id,
                    )
                    .order_by(AttemptQuestion.order_index),
                )
            ).all(),
        )

    restarted_attempts, _results = build_services(session_factory)
    resumed = await restarted_attempts.start_or_resume(
        flow.access_code,
        "100",
    )
    async with session_factory() as session:
        second_order = list(
            (
                await session.scalars(
                    select(Question.position)
                    .join(
                        AttemptQuestion,
                        AttemptQuestion.question_id == Question.id,
                    )
                    .where(
                        AttemptQuestion.attempt_id == resumed.attempt_id,
                    )
                    .order_by(AttemptQuestion.order_index),
                )
            ).all(),
        )

    assert first_order == second_order
    assert sorted(first_order) == list(range(1, 13))


@pytest.mark.asyncio
async def test_restart_selects_next_unanswered_question(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    flow = await create_flow(session_factory, question_count=3)
    attempts, _results = build_services(session_factory)
    first = await attempts.start_or_resume(flow.access_code, "100")
    outcome = await attempts.answer_question(
        first.attempt_question_id,
        2,
        "100",
    )
    assert outcome.next_question is not None

    restarted_attempts, _results = build_services(session_factory)
    resumed = await restarted_attempts.resume_active(
        first.attempt_id,
        "100",
    )

    assert resumed is not None
    assert (
        resumed.attempt_question_id
        == outcome.next_question.attempt_question_id
    )


@pytest.mark.asyncio
async def test_double_callback_does_not_create_second_answer(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    flow = await create_flow(session_factory, question_count=2)
    attempts, _results = build_services(session_factory)
    first = await attempts.start_or_resume(flow.access_code, "100")

    first_outcome = await attempts.answer_question(
        first.attempt_question_id,
        4,
        "100",
    )
    duplicate_outcome = await attempts.answer_question(
        first.attempt_question_id,
        4,
        "100",
    )

    assert first_outcome.duplicate is False
    assert duplicate_outcome.duplicate is True
    async with session_factory() as session:
        answered_count = await session.scalar(
            select(func.count(AttemptQuestion.id)).where(
                AttemptQuestion.attempt_id == first.attempt_id,
                AttemptQuestion.selected_value.is_not(None),
            ),
        )
    assert answered_count == 1


@pytest.mark.asyncio
async def test_bound_code_rejects_another_max_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    flow = await create_flow(
        session_factory,
        patient_max_user_id="owner",
    )
    attempts, _results = build_services(session_factory)

    with pytest.raises(AssignmentAccessDeniedError):
        await attempts.start_or_resume(flow.access_code, "stranger")


@pytest.mark.asyncio
async def test_completed_assignment_cannot_be_reused(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    flow = await create_flow(session_factory, question_count=1)
    attempts, _results = build_services(session_factory)
    await answer_until_complete(attempts, flow.access_code, "100")

    with pytest.raises(AssignmentAccessDeniedError):
        await attempts.start_or_resume(flow.access_code, "100")


@pytest.mark.asyncio
async def test_two_assignments_create_separate_attempts(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first_flow = await create_flow(
        session_factory,
        access_code="11111111",
        patient_code="111111",
        question_count=1,
    )
    attempts, _results = build_services(session_factory)
    first_attempt_id = await answer_until_complete(
        attempts,
        first_flow.access_code,
        "100",
    )

    async with session_factory() as session:
        async with session.begin():
            second_assignment = DbTestAssignment(
                patient_id=first_flow.patient_id,
                questionnaire_id=first_flow.questionnaire_id,
                access_code="22222222",
                created_by_admin_max_user_id="999",
            )
            session.add(second_assignment)

    second_attempt_id = await answer_until_complete(
        attempts,
        "22222222",
        "100",
    )

    assert first_attempt_id != second_attempt_id
    async with session_factory() as session:
        count = await session.scalar(
            select(func.count(DbTestAttempt.id)).where(
                DbTestAttempt.patient_id == first_flow.patient_id,
            ),
        )
    assert count == 2


@pytest.mark.asyncio
async def test_category_results_are_not_duplicated(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    flow = await create_flow(session_factory, question_count=1)
    attempts, results = build_services(session_factory)
    attempt_id = await answer_until_complete(
        attempts,
        flow.access_code,
        "100",
    )

    async with session_factory() as session:
        async with session.begin():
            attempt = await session.get(DbTestAttempt, attempt_id)
            assert attempt is not None
            assert await results.complete_attempt(
                session,
                attempt,
                "100",
            )

    async with session_factory() as session:
        count = await session.scalar(
            select(func.count(AttemptCategoryResult.id)).where(
                AttemptCategoryResult.attempt_id == attempt_id,
            ),
        )
    assert count == 1


@pytest.mark.asyncio
async def test_lie_scale_without_rules_is_not_configured(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    flow = await create_flow(
        session_factory,
        question_count=1,
        lie_positions={1},
    )
    attempts, _results = build_services(session_factory)
    attempt_id = await answer_until_complete(
        attempts,
        flow.access_code,
        "100",
        value=5,
    )

    async with session_factory() as session:
        lie_result = await session.scalar(
            select(AttemptLieResult).where(
                AttemptLieResult.attempt_id == attempt_id,
            ),
        )
    assert lie_result is not None
    assert lie_result.scoring_configured is False
    assert lie_result.score is None


@pytest.mark.asyncio
async def test_lie_scale_uses_configured_rules(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    flow = await create_flow(
        session_factory,
        question_count=1,
        lie_positions={1},
    )
    async with session_factory() as session:
        async with session.begin():
            session.add_all(
                [
                    LieQuestionAnswerScore(
                        question_id=flow.question_ids[0],
                        answer_value=answer_value,
                        points=points,
                    )
                    for answer_value, points in {
                        1: 0,
                        2: 0,
                        3: 0,
                        4: 1,
                        5: 2,
                    }.items()
                ],
            )

    attempts, _results = build_services(session_factory)
    attempt_id = await answer_until_complete(
        attempts,
        flow.access_code,
        "100",
        value=5,
    )

    async with session_factory() as session:
        lie_result = await session.scalar(
            select(AttemptLieResult).where(
                AttemptLieResult.attempt_id == attempt_id,
            ),
        )
    assert lie_result is not None
    assert lie_result.scoring_configured is True
    assert lie_result.score == 2
    assert lie_result.level_code == "reliable"


@pytest.mark.asyncio
async def test_questionnaire_seed_is_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    database = SimpleNamespace(session_factory=session_factory)

    first = await seed_questionnaire(database)
    second = await seed_questionnaire(database)

    assert first == second
    async with session_factory() as session:
        questionnaire_count = await session.scalar(
            select(func.count(Questionnaire.id)),
        )
        category_count = await session.scalar(
            select(func.count(Category.id)),
        )
        question_count = await session.scalar(
            select(func.count(Question.id)),
        )
        range_count = await session.scalar(
            select(func.count(CategoryInterpretationRange.id)),
        )
        is_active = await session.scalar(
            select(Questionnaire.is_active),
        )
    assert questionnaire_count == 1
    assert category_count == 9
    assert question_count == 90
    assert range_count == 27
    assert is_active is False
