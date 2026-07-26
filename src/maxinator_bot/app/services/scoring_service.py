from __future__ import annotations

from decimal import Decimal

from maxinator_bot.app.database.models import Question
from maxinator_bot.app.domain.constants import (
    MAX_ANSWER_VALUE,
    MIN_ANSWER_VALUE,
)
from maxinator_bot.app.domain.enums import ScoringDirection


class ScoringConfigurationError(RuntimeError):
    pass


class ScoringService:
    @staticmethod
    def validate_answer(selected_value: int) -> None:
        if (
            isinstance(selected_value, bool)
            or not isinstance(selected_value, int)
            or not MIN_ANSWER_VALUE <= selected_value <= MAX_ANSWER_VALUE
        ):
            raise ValueError("Answer must be an integer from 1 to 5")

    @classmethod
    def calculate_question_score(
        cls,
        selected_value: int,
        weight: Decimal,
        scoring_direction: ScoringDirection | None,
        *,
        is_lie_question: bool = False,
    ) -> Decimal | None:
        cls.validate_answer(selected_value)
        weight = Decimal(weight)

        if is_lie_question or scoring_direction == ScoringDirection.NONE:
            return Decimal("0")
        if scoring_direction == ScoringDirection.DIRECT:
            return Decimal(selected_value) * weight
        if scoring_direction == ScoringDirection.REVERSE:
            return Decimal(6 - selected_value) * weight
        if scoring_direction is None:
            return None
        raise ScoringConfigurationError(
            f"Unsupported scoring direction: {scoring_direction}",
        )

    @classmethod
    def score_question(
        cls,
        question: Question,
        selected_value: int,
    ) -> Decimal | None:
        return cls.calculate_question_score(
            selected_value,
            question.weight,
            question.scoring_direction,
            is_lie_question=question.is_lie_question,
        )

    @staticmethod
    def interpret_lie_score(score: int) -> tuple[str, str]:
        if score <= 3:
            return "reliable", "Ответы достоверны"
        if score <= 5:
            return (
                "possible_distortion",
                "Возможны некоторые искажения",
            )
        return (
            "high_insincerity_probability",
            "Высокая вероятность неискренности",
        )
