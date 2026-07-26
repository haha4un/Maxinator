from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from maxinator_bot.app.database.base import Base

if TYPE_CHECKING:
    from .testing import TestAssignment, TestAttempt


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        Index("ix_patients_public_code", "public_code", unique=True),
        CheckConstraint(
            "public_code ~ '^[0-9]{6}$'",
            name="public_code_format",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    public_code: Mapped[str] = mapped_column(String(32), nullable=False)
    max_user_id: Mapped[str | None] = mapped_column(String(128))
    display_name: Mapped[str | None] = mapped_column(String(255))
    admin_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    assignments: Mapped[list[TestAssignment]] = relationship(
        back_populates="patient",
    )
    attempts: Mapped[list[TestAttempt]] = relationship(
        back_populates="patient",
    )
