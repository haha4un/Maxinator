from __future__ import annotations

import re
from decimal import Decimal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from maxinator_bot.app.domain.enums import ScoringDirection


CODE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


class InterpretationPayload(BaseModel):
    min_score: Decimal
    max_score: Decimal
    level_code: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    requires_attention: bool = False

    @model_validator(mode="after")
    def validate_score_order(self) -> InterpretationPayload:
        if self.min_score > self.max_score:
            raise ValueError("Минимальный балл не может быть больше максимального")
        return self


class QuestionPayload(BaseModel):
    text: str = Field(min_length=1)
    image_url: str | None = Field(default=None, max_length=2048)
    weight: Decimal = Field(default=Decimal("1"), ge=0)
    scoring_direction: ScoringDirection = ScoringDirection.DIRECT
    is_lie_question: bool = False
    is_active: bool = True
    answer_scores: dict[int, int] = Field(default_factory=dict)

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value: str | None) -> str | None:
        if not value or not value.strip():
            return None
        value = value.strip()
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"drive.google.com", "docs.google.com"}
        ):
            raise ValueError("Картинка должна быть HTTPS-ссылкой на Google Drive")
        return value

    @field_validator("answer_scores")
    @classmethod
    def validate_answer_scores(cls, value: dict[int, int]) -> dict[int, int]:
        if any(answer not in range(1, 6) for answer in value):
            raise ValueError("Контрольные ответы должны быть от 1 до 5")
        if any(points < 0 for points in value.values()):
            raise ValueError("Контрольные баллы не могут быть отрицательными")
        return value

    @model_validator(mode="after")
    def normalize_lie_question(self) -> QuestionPayload:
        self.text = self.text.strip()
        self.image_url = self.image_url.strip() if self.image_url else None
        if self.is_lie_question:
            self.weight = Decimal("0")
            self.scoring_direction = ScoringDirection.NONE
        elif self.answer_scores:
            raise ValueError("Баллы ответов допустимы только для контрольного вопроса")
        return self


class CategoryPayload(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    questions: list[QuestionPayload] = Field(default_factory=list)
    interpretations: list[InterpretationPayload] = Field(default_factory=list)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        value = value.strip().lower()
        if not CODE_PATTERN.fullmatch(value):
            raise ValueError("Код: латиница, цифры, дефис или подчёркивание")
        return value


class QuestionnairePayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(min_length=2, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    version: int = Field(default=1, gt=0)
    is_active: bool = False
    categories: list[CategoryPayload] = Field(default_factory=list)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        value = value.strip().lower()
        if not CODE_PATTERN.fullmatch(value):
            raise ValueError("Код: латиница, цифры, дефис или подчёркивание")
        return value

    @model_validator(mode="after")
    def validate_structure(self) -> QuestionnairePayload:
        category_codes = [category.code for category in self.categories]
        if len(category_codes) != len(set(category_codes)):
            raise ValueError("Коды групп не должны повторяться")
        if self.is_active:
            if not self.categories:
                raise ValueError("Нельзя опубликовать опросник без групп")
            for category in self.categories:
                active_questions = [
                    question for question in category.questions if question.is_active
                ]
                if not active_questions:
                    raise ValueError(
                        f"В группе «{category.name}» нет активных вопросов",
                    )
                regular = [
                    question
                    for question in active_questions
                    if not question.is_lie_question
                ]
                if not regular:
                    raise ValueError(
                        f"В группе «{category.name}» нет оцениваемых вопросов",
                    )
                if any(
                    question.scoring_direction == ScoringDirection.NONE
                    for question in regular
                ):
                    raise ValueError(
                        f"В группе «{category.name}» есть вопрос без формулы",
                    )
                self._validate_ranges(category)
        return self

    @staticmethod
    def _validate_ranges(category: CategoryPayload) -> None:
        if not category.interpretations:
            raise ValueError(
                f"Для группы «{category.name}» не заданы диапазоны",
            )
        ordered = sorted(
            category.interpretations,
            key=lambda item: item.min_score,
        )
        for previous, current in zip(ordered, ordered[1:]):
            if current.min_score <= previous.max_score:
                raise ValueError(
                    f"Диапазоны группы «{category.name}» пересекаются",
                )


class QuestionnaireSummary(BaseModel):
    id: UUID
    code: str
    title: str
    version: int
    is_active: bool
    category_count: int
    question_count: int
    editable: bool
