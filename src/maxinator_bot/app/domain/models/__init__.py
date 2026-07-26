from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from math import ceil
from typing import Generic, TypeVar
from uuid import UUID


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int

    @property
    def page_count(self) -> int:
        return max(1, ceil(self.total / self.page_size))

    @property
    def has_previous(self) -> bool:
        return self.page > 0

    @property
    def has_next(self) -> bool:
        return self.page + 1 < self.page_count


@dataclass(frozen=True, slots=True)
class QuestionProgress:
    attempt_id: UUID
    attempt_question_id: UUID
    question_text: str
    current_number: int
    total: int


@dataclass(frozen=True, slots=True)
class AnswerOutcome:
    attempt_id: UUID
    next_question: QuestionProgress | None
    completed: bool
    duplicate: bool


@dataclass(frozen=True, slots=True)
class CompletedAttemptSummary:
    attempt_id: UUID
    patient_code: str
    questionnaire_title: str
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class CategoryResultView:
    category_name: str
    raw_score: Decimal
    level_title: str
    interpretation: str
    requires_attention: bool


@dataclass(frozen=True, slots=True)
class LieResultView:
    score: int | None
    level_code: str | None
    interpretation: str | None
    scoring_configured: bool


@dataclass(frozen=True, slots=True)
class AttemptResultView:
    attempt_id: UUID
    patient_code: str
    questionnaire_title: str
    assigned_at: datetime
    started_at: datetime
    completed_at: datetime
    categories: list[CategoryResultView]
    lie_result: LieResultView


@dataclass(frozen=True, slots=True)
class PendingAlertView:
    alert_id: UUID
    attempt_id: UUID
    patient_code: str
    questionnaire_title: str
    category_name: str
    level_title: str


__all__ = [
    "AnswerOutcome",
    "AttemptResultView",
    "CategoryResultView",
    "CompletedAttemptSummary",
    "LieResultView",
    "Page",
    "PendingAlertView",
    "QuestionProgress",
]
