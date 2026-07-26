from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from maxinator_bot.app.database.base import Base
from maxinator_bot.app.domain.enums import (
    AssignmentStatus,
    AttemptStatus,
    BotState,
)

if TYPE_CHECKING:
    from .patient import Patient
    from .questionnaire import Category, Question, Questionnaire


def enum_values(enum_type: type[Any]) -> list[str]:
    return [item.value for item in enum_type]


assignment_status_enum = SAEnum(
    AssignmentStatus,
    values_callable=enum_values,
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    name="assignment_status",
)
attempt_status_enum = SAEnum(
    AttemptStatus,
    values_callable=enum_values,
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    name="attempt_status",
)
bot_state_enum = SAEnum(
    BotState,
    values_callable=enum_values,
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    name="bot_state",
)


class TestAssignment(Base):
    __tablename__ = "test_assignments"
    __table_args__ = (
        Index(
            "ix_test_assignments_access_code",
            "access_code",
            unique=True,
        ),
        CheckConstraint(
            "access_code ~ '^[0-9]{8}$'",
            name="assignment_access_code_format",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("patients.id"),
        nullable=False,
        index=True,
    )
    questionnaire_id: Mapped[UUID] = mapped_column(
        ForeignKey("questionnaires.id"),
        nullable=False,
        index=True,
    )
    access_code: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[AssignmentStatus] = mapped_column(
        assignment_status_enum,
        default=AssignmentStatus.CREATED,
        server_default=AssignmentStatus.CREATED.value,
        nullable=False,
        index=True,
    )
    created_by_admin_max_user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    patient: Mapped[Patient] = relationship(back_populates="assignments")
    questionnaire: Mapped[Questionnaire] = relationship(
        back_populates="assignments",
    )
    attempt: Mapped[TestAttempt | None] = relationship(
        back_populates="assignment",
        uselist=False,
    )


class TestAttempt(Base):
    __tablename__ = "test_attempts"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id",
            name="uq_test_attempts_assignment_id",
        ),
        CheckConstraint(
            "current_question_index >= 0",
            name="current_question_index_non_negative",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    assignment_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_assignments.id"),
        nullable=False,
    )
    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("patients.id"),
        nullable=False,
        index=True,
    )
    questionnaire_id: Mapped[UUID] = mapped_column(
        ForeignKey("questionnaires.id"),
        nullable=False,
        index=True,
    )
    questionnaire_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[AttemptStatus] = mapped_column(
        attempt_status_enum,
        default=AttemptStatus.IN_PROGRESS,
        server_default=AttemptStatus.IN_PROGRESS.value,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    current_question_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    assignment: Mapped[TestAssignment] = relationship(
        back_populates="attempt",
    )
    patient: Mapped[Patient] = relationship(back_populates="attempts")
    questionnaire: Mapped[Questionnaire] = relationship(
        back_populates="attempts",
    )
    attempt_questions: Mapped[list[AttemptQuestion]] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
        order_by="AttemptQuestion.order_index",
    )
    category_results: Mapped[list[AttemptCategoryResult]] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
    )
    lie_result: Mapped[AttemptLieResult | None] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
        uselist=False,
    )
    alerts: Mapped[list[AttemptAlert]] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
    )


class AttemptQuestion(Base):
    __tablename__ = "attempt_questions"
    __table_args__ = (
        UniqueConstraint(
            "attempt_id",
            "question_id",
            name="uq_attempt_questions_attempt_question",
        ),
        UniqueConstraint(
            "attempt_id",
            "order_index",
            name="uq_attempt_questions_attempt_order",
        ),
        CheckConstraint(
            "selected_value IS NULL OR selected_value BETWEEN 1 AND 5",
            name="selected_value_range",
        ),
        CheckConstraint(
            "order_index >= 0",
            name="attempt_question_order_non_negative",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id"),
        nullable=False,
        index=True,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_value: Mapped[int | None] = mapped_column(Integer)
    calculated_category_score: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4),
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    attempt: Mapped[TestAttempt] = relationship(
        back_populates="attempt_questions",
    )
    question: Mapped[Question] = relationship(
        back_populates="attempt_questions",
    )


class AttemptCategoryResult(Base):
    __tablename__ = "attempt_category_results"
    __table_args__ = (
        UniqueConstraint(
            "attempt_id",
            "category_id",
            name="uq_attempt_category_results_attempt_category",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("categories.id"),
        nullable=False,
        index=True,
    )
    raw_score: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    min_possible_score: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
    )
    max_possible_score: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
    )
    level_code: Mapped[str] = mapped_column(String(64), nullable=False)
    level_title: Mapped[str] = mapped_column(String(255), nullable=False)
    interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    attempt: Mapped[TestAttempt] = relationship(
        back_populates="category_results",
    )
    category: Mapped[Category] = relationship(
        back_populates="attempt_results",
    )


class AttemptLieResult(Base):
    __tablename__ = "attempt_lie_results"
    __table_args__ = (
        UniqueConstraint(
            "attempt_id",
            name="uq_attempt_lie_results_attempt_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_attempts.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[int | None] = mapped_column(Integer)
    level_code: Mapped[str | None] = mapped_column(String(64))
    interpretation: Mapped[str | None] = mapped_column(Text)
    scoring_configured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    attempt: Mapped[TestAttempt] = relationship(back_populates="lie_result")


class AttemptAlert(Base):
    __tablename__ = "attempt_alerts"
    __table_args__ = (
        UniqueConstraint(
            "attempt_id",
            "category_id",
            "alert_type",
            name="uq_attempt_alerts_attempt_category_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("categories.id"),
        nullable=False,
        index=True,
    )
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    attempt: Mapped[TestAttempt] = relationship(back_populates="alerts")


class BotSession(Base):
    __tablename__ = "bot_sessions"

    max_user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    state: Mapped[BotState] = mapped_column(
        bot_state_enum,
        default=BotState.IDLE,
        server_default=BotState.IDLE.value,
        nullable=False,
    )
    selected_patient_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("patients.id"),
    )
    selected_questionnaire_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("questionnaires.id"),
    )
    active_attempt_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("test_attempts.id"),
    )
    page: Mapped[int | None] = mapped_column(Integer)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
