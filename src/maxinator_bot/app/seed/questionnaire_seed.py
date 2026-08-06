from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from maxinator_bot.app.config import get_settings
from maxinator_bot.app.database import Database
from maxinator_bot.app.database.models import (
    Category,
    CategoryInterpretationRange,
    LieQuestionAnswerScore,
    Question,
    Questionnaire,
)
from maxinator_bot.app.seed.questionnaire_data import (
    CATEGORIES,
    LIE_QUESTION_ANSWER_SCORES,
    QUESTIONNAIRE_CODE,
    QUESTIONNAIRE_IS_ACTIVE,
    QUESTIONNAIRE_TITLE,
    QUESTIONNAIRE_VERSION,
    validate_questionnaire_data,
)


@dataclass(frozen=True, slots=True)
class SeedSummary:
    categories: int
    questions: int
    interpretation_ranges: int
    lie_scoring_rules: int


async def seed_questionnaire(database: Database | None = None) -> SeedSummary:
    validate_questionnaire_data()
    owns_database = database is None
    database = database or Database(get_settings())

    try:
        async with database.session_factory() as session:
            async with session.begin():
                return await _seed(session)
    finally:
        if owns_database:
            await database.dispose()


async def _seed(session: AsyncSession) -> SeedSummary:
    questionnaire = await session.scalar(
        select(Questionnaire).where(
            Questionnaire.code == QUESTIONNAIRE_CODE,
        ),
    )
    if questionnaire is None:
        questionnaire = Questionnaire(
            code=QUESTIONNAIRE_CODE,
            title=QUESTIONNAIRE_TITLE,
            description=(
                "Опросник из 90 вопросов. Направления подсчёта "
                "обычных вопросов требуют подтверждения."
            ),
            version=QUESTIONNAIRE_VERSION,
            is_active=QUESTIONNAIRE_IS_ACTIVE,
        )
        session.add(questionnaire)
        await session.flush()
    else:
        questionnaire.title = QUESTIONNAIRE_TITLE
        questionnaire.version = QUESTIONNAIRE_VERSION
        questionnaire.is_active = QUESTIONNAIRE_IS_ACTIVE

    existing_categories = {
        category.code: category
        for category in (
            await session.scalars(
                select(Category).where(
                    Category.questionnaire_id == questionnaire.id,
                ),
            )
        ).all()
    }
    existing_questions = {
        question.position: question
        for question in (
            await session.scalars(
                select(Question).where(
                    Question.questionnaire_id == questionnaire.id,
                ),
            )
        ).all()
    }

    question_position = 0
    seeded_questions: dict[int, Question] = {}
    interpretation_count = 0
    for category_position, category_data in enumerate(CATEGORIES, start=1):
        category = existing_categories.get(category_data.code)
        if category is None:
            category = Category(
                questionnaire_id=questionnaire.id,
                code=category_data.code,
                name=category_data.name,
                position=category_position,
            )
            session.add(category)
            await session.flush()
        else:
            category.name = category_data.name
            category.position = category_position

        ranges = {
            (
                Decimal(item.min_score),
                Decimal(item.max_score),
            ): item
            for item in (
                await session.scalars(
                    select(CategoryInterpretationRange).where(
                        CategoryInterpretationRange.category_id
                        == category.id,
                    ),
                )
            ).all()
        }
        for range_data in category_data.interpretations:
            key = (range_data.min_score, range_data.max_score)
            interpretation_range = ranges.get(key)
            if interpretation_range is None:
                interpretation_range = CategoryInterpretationRange(
                    category_id=category.id,
                    min_score=range_data.min_score,
                    max_score=range_data.max_score,
                    level_code=range_data.level_code,
                    title=range_data.title,
                    description=range_data.description,
                    requires_attention=range_data.requires_attention,
                )
                session.add(interpretation_range)
            else:
                interpretation_range.level_code = range_data.level_code
                interpretation_range.title = range_data.title
                interpretation_range.description = range_data.description
                interpretation_range.requires_attention = (
                    range_data.requires_attention
                )
            interpretation_count += 1

        for question_data in category_data.questions:
            question_position += 1
            question = existing_questions.get(question_position)
            if question is None:
                question = Question(
                    questionnaire_id=questionnaire.id,
                    category_id=category.id,
                    text=question_data.text,
                    position=question_position,
                    weight=question_data.weight,
                    scoring_direction=question_data.scoring_direction,
                    is_lie_question=question_data.is_lie_question,
                    is_active=True,
                )
                session.add(question)
            else:
                question.category_id = category.id
                question.text = question_data.text
                question.weight = question_data.weight
                # Preserve scoring configured later through the editor or a
                # migration when the legacy seed has no direction to offer.
                if question_data.scoring_direction is not None:
                    question.scoring_direction = (
                        question_data.scoring_direction
                    )
                question.is_lie_question = question_data.is_lie_question
                question.is_active = True
            seeded_questions[question_position] = question

    await session.flush()
    lie_rule_count = await _seed_lie_rules(session, seeded_questions)
    return SeedSummary(
        categories=len(CATEGORIES),
        questions=question_position,
        interpretation_ranges=interpretation_count,
        lie_scoring_rules=lie_rule_count,
    )


async def _seed_lie_rules(
    session: AsyncSession,
    questions: dict[int, Question],
) -> int:
    configured_count = 0
    for question_position, answer_scores in (
        LIE_QUESTION_ANSWER_SCORES.items()
    ):
        question = questions[question_position]
        existing_rules = {
            rule.answer_value: rule
            for rule in (
                await session.scalars(
                    select(LieQuestionAnswerScore).where(
                        LieQuestionAnswerScore.question_id == question.id,
                    ),
                )
            ).all()
        }
        for answer_value, points in answer_scores.items():
            rule = existing_rules.get(answer_value)
            if rule is None:
                session.add(
                    LieQuestionAnswerScore(
                        question_id=question.id,
                        answer_value=answer_value,
                        points=points,
                    ),
                )
            else:
                rule.points = points
            configured_count += 1
    return configured_count


def main() -> None:
    summary = asyncio.run(seed_questionnaire())
    print(
        "Seed completed: "
        f"{summary.categories} categories, "
        f"{summary.questions} questions, "
        f"{summary.interpretation_ranges} ranges, "
        f"{summary.lie_scoring_rules} lie rules",
    )


if __name__ == "__main__":
    main()
