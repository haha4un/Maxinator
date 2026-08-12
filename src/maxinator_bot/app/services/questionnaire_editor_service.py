from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from maxinator_bot.app.database.models import (
    Category,
    CategoryInterpretationRange,
    LieQuestionAnswerScore,
    Question,
    Questionnaire,
    TestAssignment,
)
from maxinator_bot.web.schemas import (
    CategoryPayload,
    QuestionnairePayload,
    QuestionnaireSummary,
)


class QuestionnaireNotFoundError(RuntimeError):
    pass


class QuestionnaireLockedError(RuntimeError):
    pass


class QuestionnaireCodeConflictError(RuntimeError):
    pass


class QuestionnaireEditorService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory

    async def list_questionnaires(self) -> list[QuestionnaireSummary]:
        async with self.session_factory() as session:
            assignment_counts = (
                select(
                    TestAssignment.questionnaire_id,
                    func.count(TestAssignment.id).label("assignment_count"),
                )
                .group_by(TestAssignment.questionnaire_id)
                .subquery()
            )
            statement = (
                select(
                    Questionnaire,
                    func.count(func.distinct(Category.id)).label("category_count"),
                    func.count(func.distinct(Question.id)).label("question_count"),
                    func.coalesce(
                        assignment_counts.c.assignment_count,
                        0,
                    ).label("assignment_count"),
                )
                .outerjoin(Category, Category.questionnaire_id == Questionnaire.id)
                .outerjoin(Question, Question.questionnaire_id == Questionnaire.id)
                .outerjoin(
                    assignment_counts,
                    assignment_counts.c.questionnaire_id == Questionnaire.id,
                )
                .group_by(
                    Questionnaire.id,
                    assignment_counts.c.assignment_count,
                )
                .order_by(Questionnaire.created_at.desc())
            )
            rows = (await session.execute(statement)).all()
            return [
                QuestionnaireSummary(
                    id=questionnaire.id,
                    code=questionnaire.code,
                    title=questionnaire.title,
                    version=questionnaire.version,
                    is_active=questionnaire.is_active,
                    category_count=category_count,
                    question_count=question_count,
                    editable=assignment_count == 0,
                )
                for (
                    questionnaire,
                    category_count,
                    question_count,
                    assignment_count,
                ) in rows
            ]

    async def get_questionnaire(
        self,
        questionnaire_id: UUID,
    ) -> QuestionnairePayload:
        async with self.session_factory() as session:
            questionnaire = await self._load(session, questionnaire_id)
            if questionnaire is None:
                raise QuestionnaireNotFoundError
            return self._serialize(questionnaire)

    async def create_questionnaire(
        self,
        payload: QuestionnairePayload,
    ) -> UUID:
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    questionnaire = Questionnaire(
                        code=payload.code,
                        title=payload.title,
                        description=payload.description,
                        version=payload.version,
                        is_active=payload.is_active,
                    )
                    session.add(questionnaire)
                    await session.flush()
                    self._add_structure(session, questionnaire, payload)
                return questionnaire.id
        except IntegrityError as exc:
            raise QuestionnaireCodeConflictError from exc

    async def update_questionnaire(
        self,
        questionnaire_id: UUID,
        payload: QuestionnairePayload,
    ) -> None:
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    questionnaire = await self._load(
                        session,
                        questionnaire_id,
                        for_update=True,
                    )
                    if questionnaire is None:
                        raise QuestionnaireNotFoundError
                    if await self._has_assignments(session, questionnaire_id):
                        raise QuestionnaireLockedError

                    questionnaire.code = payload.code
                    questionnaire.title = payload.title
                    questionnaire.description = payload.description
                    questionnaire.version = payload.version
                    questionnaire.is_active = payload.is_active

                    await session.execute(
                        delete(Category).where(
                            Category.questionnaire_id == questionnaire_id,
                        ),
                    )
                    await session.flush()
                    self._add_structure(session, questionnaire, payload)
        except IntegrityError as exc:
            raise QuestionnaireCodeConflictError from exc

    async def clone_questionnaire(
        self,
        questionnaire_id: UUID,
    ) -> UUID:
        payload = await self.get_questionnaire(questionnaire_id)
        payload.code = await self._next_clone_code(payload.code)
        payload.version += 1
        payload.is_active = False
        return await self.create_questionnaire(payload)

    async def delete_questionnaire(self, questionnaire_id: UUID) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                questionnaire = await session.get(
                    Questionnaire,
                    questionnaire_id,
                    with_for_update=True,
                )
                if questionnaire is None:
                    raise QuestionnaireNotFoundError
                if await self._has_assignments(session, questionnaire_id):
                    raise QuestionnaireLockedError
                await session.delete(questionnaire)

    async def _next_clone_code(self, base_code: str) -> str:
        root = base_code[:54]
        async with self.session_factory() as session:
            existing = set(
                (
                    await session.scalars(
                        select(Questionnaire.code).where(
                            Questionnaire.code.like(f"{root}_v%"),
                        ),
                    )
                ).all(),
            )
        index = 2
        while f"{root}_v{index}" in existing:
            index += 1
        return f"{root}_v{index}"

    @staticmethod
    async def _has_assignments(
        session: AsyncSession,
        questionnaire_id: UUID,
    ) -> bool:
        count = await session.scalar(
            select(func.count(TestAssignment.id)).where(
                TestAssignment.questionnaire_id == questionnaire_id,
            ),
        )
        return bool(count)

    @staticmethod
    async def _load(
        session: AsyncSession,
        questionnaire_id: UUID,
        *,
        for_update: bool = False,
    ) -> Questionnaire | None:
        statement = (
            select(Questionnaire)
            .where(Questionnaire.id == questionnaire_id)
            .options(
                selectinload(Questionnaire.categories)
                .selectinload(Category.questions)
                .selectinload(Question.lie_answer_scores),
                selectinload(Questionnaire.categories).selectinload(
                    Category.interpretation_ranges,
                ),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    @staticmethod
    def _add_structure(
        session: AsyncSession,
        questionnaire: Questionnaire,
        payload: QuestionnairePayload,
    ) -> None:
        question_position = 1
        for category_position, category_data in enumerate(
            payload.categories,
            start=1,
        ):
            category = Category(
                questionnaire_id=questionnaire.id,
                code=category_data.code,
                name=category_data.name,
                description=category_data.description,
                position=category_position,
            )
            session.add(category)
            for question_data in category_data.questions:
                question = Question(
                    questionnaire_id=questionnaire.id,
                    category=category,
                    text=question_data.text,
                    image_url=question_data.image_url,
                    position=question_position,
                    weight=question_data.weight,
                    scoring_direction=question_data.scoring_direction,
                    is_lie_question=question_data.is_lie_question,
                    is_active=question_data.is_active,
                )
                session.add(question)
                for answer_value, points in question_data.answer_scores.items():
                    session.add(
                        LieQuestionAnswerScore(
                            question=question,
                            answer_value=answer_value,
                            points=points,
                        ),
                    )
                question_position += 1
            for range_data in category_data.interpretations:
                session.add(
                    CategoryInterpretationRange(
                        category=category,
                        min_score=range_data.min_score,
                        max_score=range_data.max_score,
                        level_code=range_data.level_code,
                        title=range_data.title,
                        description=range_data.description,
                        requires_attention=range_data.requires_attention,
                    ),
                )

    @staticmethod
    def _serialize(questionnaire: Questionnaire) -> QuestionnairePayload:
        return QuestionnairePayload(
            code=questionnaire.code,
            title=questionnaire.title,
            description=questionnaire.description,
            version=questionnaire.version,
            is_active=questionnaire.is_active,
            categories=[
                CategoryPayload(
                    code=category.code,
                    name=category.name,
                    description=category.description,
                    questions=[
                        {
                            "text": question.text,
                            "image_url": question.image_url,
                            "weight": question.weight,
                            "scoring_direction": question.scoring_direction,
                            "is_lie_question": question.is_lie_question,
                            "is_active": question.is_active,
                            "answer_scores": {
                                rule.answer_value: rule.points
                                for rule in question.lie_answer_scores
                            },
                        }
                        for question in category.questions
                    ],
                    interpretations=[
                        {
                            "min_score": item.min_score,
                            "max_score": item.max_score,
                            "level_code": item.level_code,
                            "title": item.title,
                            "description": item.description,
                            "requires_attention": item.requires_attention,
                        }
                        for item in category.interpretation_ranges
                    ],
                )
                for category in questionnaire.categories
            ],
        )
