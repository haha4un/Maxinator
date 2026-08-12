from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from maxinator_bot.app.database.base import Base
from maxinator_bot.app.domain.enums import ScoringDirection

if TYPE_CHECKING:
    from .testing import (
        AttemptCategoryResult,
        AttemptQuestion,
        TestAssignment,
        TestAttempt,
    )


def enum_values(enum_type: type[ScoringDirection]) -> list[str]:
    return [item.value for item in enum_type]


scoring_direction_enum = SAEnum(
    ScoringDirection,
    values_callable=enum_values,
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    name="scoring_direction",
)


class Questionnaire(Base):
    __tablename__ = "questionnaires"
    __table_args__ = (
        Index("ix_questionnaires_code", "code", unique=True),
        CheckConstraint("version > 0", name="questionnaire_version_positive"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    categories: Mapped[list[Category]] = relationship(
        back_populates="questionnaire",
        cascade="all, delete-orphan",
        order_by="Category.position",
    )
    questions: Mapped[list[Question]] = relationship(
        back_populates="questionnaire",
        cascade="all, delete-orphan",
        order_by="Question.position",
    )
    assignments: Mapped[list[TestAssignment]] = relationship(
        back_populates="questionnaire",
    )
    attempts: Mapped[list[TestAttempt]] = relationship(
        back_populates="questionnaire",
    )


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint(
            "questionnaire_id",
            "code",
            name="uq_categories_questionnaire_code",
        ),
        UniqueConstraint(
            "questionnaire_id",
            "position",
            name="uq_categories_questionnaire_position",
        ),
        CheckConstraint(
            "position > 0",
            name="category_position_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    questionnaire_id: Mapped[UUID] = mapped_column(
        ForeignKey("questionnaires.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    questionnaire: Mapped[Questionnaire] = relationship(
        back_populates="categories",
    )
    questions: Mapped[list[Question]] = relationship(
        back_populates="category",
        order_by="Question.position",
    )
    interpretation_ranges: Mapped[list[CategoryInterpretationRange]] = (
        relationship(
            back_populates="category",
            cascade="all, delete-orphan",
            order_by="CategoryInterpretationRange.min_score",
        )
    )
    attempt_results: Mapped[list[AttemptCategoryResult]] = relationship(
        back_populates="category",
    )


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint(
            "questionnaire_id",
            "position",
            name="uq_questions_questionnaire_position",
        ),
        CheckConstraint(
            "weight >= 0",
            name="question_weight_non_negative",
        ),
        CheckConstraint(
            "is_lie_question = false OR "
            "(weight = 0 AND scoring_direction IS NOT NULL "
            "AND scoring_direction = 'none')",
            name="lie_question_scoring",
        ),
        CheckConstraint(
            "position > 0",
            name="question_position_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    questionnaire_id: Mapped[UUID] = mapped_column(
        ForeignKey("questionnaires.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        default=Decimal("1"),
        nullable=False,
    )
    scoring_direction: Mapped[ScoringDirection | None] = mapped_column(
        scoring_direction_enum,
        nullable=True,
    )
    is_lie_question: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    questionnaire: Mapped[Questionnaire] = relationship(
        back_populates="questions",
    )
    category: Mapped[Category] = relationship(back_populates="questions")
    attempt_questions: Mapped[list[AttemptQuestion]] = relationship(
        back_populates="question",
    )
    lie_answer_scores: Mapped[list[LieQuestionAnswerScore]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )


class CategoryInterpretationRange(Base):
    __tablename__ = "category_interpretation_ranges"
    __table_args__ = (
        UniqueConstraint(
            "category_id",
            "min_score",
            "max_score",
            name="uq_category_interpretation_range",
        ),
        CheckConstraint(
            "min_score <= max_score",
            name="interpretation_score_order",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    min_score: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    max_score: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    level_code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requires_attention: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    category: Mapped[Category] = relationship(
        back_populates="interpretation_ranges",
    )


class LieQuestionAnswerScore(Base):
    __tablename__ = "lie_question_answer_scores"
    __table_args__ = (
        UniqueConstraint(
            "question_id",
            "answer_value",
            name="uq_lie_question_answer_score",
        ),
        CheckConstraint(
            "answer_value BETWEEN 1 AND 5",
            name="lie_answer_value_range",
        ),
        CheckConstraint(
            "points >= 0",
            name="lie_points_non_negative",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    answer_value: Mapped[int] = mapped_column(Integer, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)

    question: Mapped[Question] = relationship(
        back_populates="lie_answer_scores",
    )
