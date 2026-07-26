from decimal import Decimal

from maxinator_bot.app.domain.enums import ScoringDirection
from maxinator_bot.app.services.scoring_service import ScoringService


def test_direct_score() -> None:
    score = ScoringService.calculate_question_score(
        4,
        Decimal("1"),
        ScoringDirection.DIRECT,
    )

    assert score == Decimal("4")


def test_reverse_score() -> None:
    score = ScoringService.calculate_question_score(
        2,
        Decimal("1"),
        ScoringDirection.REVERSE,
    )

    assert score == Decimal("4")


def test_decimal_weight_is_applied() -> None:
    score = ScoringService.calculate_question_score(
        3,
        Decimal("1.25"),
        ScoringDirection.DIRECT,
    )

    assert score == Decimal("3.75")


def test_lie_question_has_zero_thematic_score() -> None:
    score = ScoringService.calculate_question_score(
        5,
        Decimal("9.5"),
        ScoringDirection.DIRECT,
        is_lie_question=True,
    )

    assert score == Decimal("0")
