from decimal import Decimal

from maxinator_bot.app.domain.enums import ScoringDirection
from maxinator_bot.app.seed.questionnaire_data import (
    CATEGORIES,
    validate_questionnaire_data,
)


def test_seed_contains_ninety_questions() -> None:
    validate_questionnaire_data()

    assert len(CATEGORIES) == 9
    assert sum(len(category.questions) for category in CATEGORIES) == 90


def test_seed_has_two_lie_questions_per_category() -> None:
    for category in CATEGORIES:
        lie_questions = [
            question
            for question in category.questions
            if question.is_lie_question
        ]

        assert len(lie_questions) == 2
        assert all(
            question.weight == Decimal("0")
            and question.scoring_direction == ScoringDirection.NONE
            for question in lie_questions
        )


def test_unconfirmed_questions_use_explicit_defaults() -> None:
    regular_questions = [
        question
        for category in CATEGORIES
        for question in category.questions
        if not question.is_lie_question
    ]

    assert len(regular_questions) == 72
    assert all(
        question.weight == Decimal("1")
        and question.scoring_direction is None
        for question in regular_questions
    )
