"""Initial questionnaire schema.

Revision ID: 20260725_0001
Revises:
Create Date: 2026-07-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260725_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


assignment_status = sa.Enum(
    "created",
    "in_progress",
    "completed",
    "cancelled",
    "expired",
    name="assignment_status",
    native_enum=False,
    create_constraint=True,
)
attempt_status = sa.Enum(
    "in_progress",
    "completed",
    "cancelled",
    name="attempt_status",
    native_enum=False,
    create_constraint=True,
)
bot_state = sa.Enum(
    "idle",
    "admin_menu",
    "choosing_patient",
    "entering_patient_code",
    "choosing_questionnaire",
    "entering_assignment_code",
    "taking_questionnaire",
    "viewing_results",
    name="bot_state",
    native_enum=False,
    create_constraint=True,
)
scoring_direction = sa.Enum(
    "direct",
    "reverse",
    "none",
    name="scoring_direction",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    op.create_table(
        "patients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_code", sa.String(length=32), nullable=False),
        sa.Column("max_user_id", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("admin_comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "public_code ~ '^[0-9]{6}$'",
            name="public_code_format",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_patients"),
    )
    op.create_index(
        "ix_patients_public_code",
        "patients",
        ["public_code"],
        unique=True,
    )

    op.create_table(
        "questionnaires",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "version > 0",
            name="questionnaire_version_positive",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_questionnaires"),
    )
    op.create_index(
        "ix_questionnaires_code",
        "questionnaires",
        ["code"],
        unique=True,
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("questionnaire_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "position > 0",
            name="category_position_positive",
        ),
        sa.ForeignKeyConstraint(
            ["questionnaire_id"],
            ["questionnaires.id"],
            name="fk_categories_questionnaire_id_questionnaires",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.UniqueConstraint(
            "questionnaire_id",
            "code",
            name="uq_categories_questionnaire_code",
        ),
        sa.UniqueConstraint(
            "questionnaire_id",
            "position",
            name="uq_categories_questionnaire_position",
        ),
    )
    op.create_index(
        "ix_categories_questionnaire_id",
        "categories",
        ["questionnaire_id"],
        unique=False,
    )

    op.create_table(
        "questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("questionnaire_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("scoring_direction", scoring_direction, nullable=True),
        sa.Column(
            "is_lie_question",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "is_lie_question = false OR "
            "(weight = 0 AND scoring_direction IS NOT NULL "
            "AND scoring_direction = 'none')",
            name="lie_question_scoring",
        ),
        sa.CheckConstraint(
            "position > 0",
            name="question_position_positive",
        ),
        sa.CheckConstraint(
            "weight >= 0",
            name="question_weight_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_questions_category_id_categories",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["questionnaire_id"],
            ["questionnaires.id"],
            name="fk_questions_questionnaire_id_questionnaires",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_questions"),
        sa.UniqueConstraint(
            "questionnaire_id",
            "position",
            name="uq_questions_questionnaire_position",
        ),
    )
    op.create_index(
        "ix_questions_category_id",
        "questions",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        "ix_questions_questionnaire_id",
        "questions",
        ["questionnaire_id"],
        unique=False,
    )

    op.create_table(
        "category_interpretation_ranges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column(
            "min_score",
            sa.Numeric(precision=14, scale=4),
            nullable=False,
        ),
        sa.Column(
            "max_score",
            sa.Numeric(precision=14, scale=4),
            nullable=False,
        ),
        sa.Column("level_code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "requires_attention",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "min_score <= max_score",
            name="interpretation_score_order",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=(
                "fk_category_interpretation_ranges_category_id_categories"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_category_interpretation_ranges",
        ),
        sa.UniqueConstraint(
            "category_id",
            "min_score",
            "max_score",
            name="uq_category_interpretation_range",
        ),
    )
    op.create_index(
        "ix_category_interpretation_ranges_category_id",
        "category_interpretation_ranges",
        ["category_id"],
        unique=False,
    )

    op.create_table(
        "lie_question_answer_scores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("answer_value", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "answer_value BETWEEN 1 AND 5",
            name="lie_answer_value_range",
        ),
        sa.CheckConstraint(
            "points >= 0",
            name="lie_points_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name="fk_lie_question_answer_scores_question_id_questions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lie_question_answer_scores"),
        sa.UniqueConstraint(
            "question_id",
            "answer_value",
            name="uq_lie_question_answer_score",
        ),
    )
    op.create_index(
        "ix_lie_question_answer_scores_question_id",
        "lie_question_answer_scores",
        ["question_id"],
        unique=False,
    )

    op.create_table(
        "test_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("questionnaire_id", sa.Uuid(), nullable=False),
        sa.Column("access_code", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            assignment_status,
            server_default="created",
            nullable=False,
        ),
        sa.Column(
            "created_by_admin_max_user_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "access_code ~ '^[0-9]{8}$'",
            name="assignment_access_code_format",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
            name="fk_test_assignments_patient_id_patients",
        ),
        sa.ForeignKeyConstraint(
            ["questionnaire_id"],
            ["questionnaires.id"],
            name="fk_test_assignments_questionnaire_id_questionnaires",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_assignments"),
    )
    op.create_index(
        "ix_test_assignments_access_code",
        "test_assignments",
        ["access_code"],
        unique=True,
    )
    op.create_index(
        "ix_test_assignments_patient_id",
        "test_assignments",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        "ix_test_assignments_questionnaire_id",
        "test_assignments",
        ["questionnaire_id"],
        unique=False,
    )
    op.create_index(
        "ix_test_assignments_status",
        "test_assignments",
        ["status"],
        unique=False,
    )

    op.create_table(
        "test_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("questionnaire_id", sa.Uuid(), nullable=False),
        sa.Column("questionnaire_version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            attempt_status,
            server_default="in_progress",
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "current_question_index",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.CheckConstraint(
            "current_question_index >= 0",
            name="current_question_index_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["test_assignments.id"],
            name="fk_test_attempts_assignment_id_test_assignments",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
            name="fk_test_attempts_patient_id_patients",
        ),
        sa.ForeignKeyConstraint(
            ["questionnaire_id"],
            ["questionnaires.id"],
            name="fk_test_attempts_questionnaire_id_questionnaires",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_test_attempts"),
        sa.UniqueConstraint(
            "assignment_id",
            name="uq_test_attempts_assignment_id",
        ),
    )
    op.create_index(
        "ix_test_attempts_patient_id",
        "test_attempts",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        "ix_test_attempts_questionnaire_id",
        "test_attempts",
        ["questionnaire_id"],
        unique=False,
    )
    op.create_index(
        "ix_test_attempts_status",
        "test_attempts",
        ["status"],
        unique=False,
    )

    op.create_table(
        "attempt_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("selected_value", sa.Integer(), nullable=True),
        sa.Column(
            "calculated_category_score",
            sa.Numeric(precision=14, scale=4),
            nullable=True,
        ),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "order_index >= 0",
            name="attempt_question_order_non_negative",
        ),
        sa.CheckConstraint(
            "selected_value IS NULL OR selected_value BETWEEN 1 AND 5",
            name="selected_value_range",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["test_attempts.id"],
            name="fk_attempt_questions_attempt_id_test_attempts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name="fk_attempt_questions_question_id_questions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_attempt_questions"),
        sa.UniqueConstraint(
            "attempt_id",
            "order_index",
            name="uq_attempt_questions_attempt_order",
        ),
        sa.UniqueConstraint(
            "attempt_id",
            "question_id",
            name="uq_attempt_questions_attempt_question",
        ),
    )
    op.create_index(
        "ix_attempt_questions_attempt_id",
        "attempt_questions",
        ["attempt_id"],
        unique=False,
    )
    op.create_index(
        "ix_attempt_questions_question_id",
        "attempt_questions",
        ["question_id"],
        unique=False,
    )

    op.create_table(
        "attempt_category_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column(
            "raw_score",
            sa.Numeric(precision=14, scale=4),
            nullable=False,
        ),
        sa.Column(
            "min_possible_score",
            sa.Numeric(precision=14, scale=4),
            nullable=False,
        ),
        sa.Column(
            "max_possible_score",
            sa.Numeric(precision=14, scale=4),
            nullable=False,
        ),
        sa.Column("level_code", sa.String(length=64), nullable=False),
        sa.Column("level_title", sa.String(length=255), nullable=False),
        sa.Column("interpretation", sa.Text(), nullable=False),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["test_attempts.id"],
            name=(
                "fk_attempt_category_results_attempt_id_test_attempts"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_attempt_category_results_category_id_categories",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_attempt_category_results"),
        sa.UniqueConstraint(
            "attempt_id",
            "category_id",
            name="uq_attempt_category_results_attempt_category",
        ),
    )
    op.create_index(
        "ix_attempt_category_results_attempt_id",
        "attempt_category_results",
        ["attempt_id"],
        unique=False,
    )
    op.create_index(
        "ix_attempt_category_results_category_id",
        "attempt_category_results",
        ["category_id"],
        unique=False,
    )

    op.create_table(
        "attempt_lie_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("level_code", sa.String(length=64), nullable=True),
        sa.Column("interpretation", sa.Text(), nullable=True),
        sa.Column("scoring_configured", sa.Boolean(), nullable=False),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["test_attempts.id"],
            name="fk_attempt_lie_results_attempt_id_test_attempts",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_attempt_lie_results"),
        sa.UniqueConstraint(
            "attempt_id",
            name="uq_attempt_lie_results_attempt_id",
        ),
    )

    op.create_table(
        "attempt_alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "acknowledged_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["test_attempts.id"],
            name="fk_attempt_alerts_attempt_id_test_attempts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_attempt_alerts_category_id_categories",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_attempt_alerts"),
        sa.UniqueConstraint(
            "attempt_id",
            "category_id",
            "alert_type",
            name="uq_attempt_alerts_attempt_category_type",
        ),
    )
    op.create_index(
        "ix_attempt_alerts_attempt_id",
        "attempt_alerts",
        ["attempt_id"],
        unique=False,
    )
    op.create_index(
        "ix_attempt_alerts_category_id",
        "attempt_alerts",
        ["category_id"],
        unique=False,
    )

    op.create_table(
        "bot_sessions",
        sa.Column("max_user_id", sa.String(length=128), nullable=False),
        sa.Column(
            "state",
            bot_state,
            server_default="idle",
            nullable=False,
        ),
        sa.Column("selected_patient_id", sa.Uuid(), nullable=True),
        sa.Column("selected_questionnaire_id", sa.Uuid(), nullable=True),
        sa.Column("active_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["active_attempt_id"],
            ["test_attempts.id"],
            name="fk_bot_sessions_active_attempt_id_test_attempts",
        ),
        sa.ForeignKeyConstraint(
            ["selected_patient_id"],
            ["patients.id"],
            name="fk_bot_sessions_selected_patient_id_patients",
        ),
        sa.ForeignKeyConstraint(
            ["selected_questionnaire_id"],
            ["questionnaires.id"],
            name="fk_bot_sessions_selected_questionnaire_id_questionnaires",
        ),
        sa.PrimaryKeyConstraint("max_user_id", name="pk_bot_sessions"),
    )


def downgrade() -> None:
    op.drop_table("bot_sessions")
    op.drop_index(
        "ix_attempt_alerts_category_id",
        table_name="attempt_alerts",
    )
    op.drop_index(
        "ix_attempt_alerts_attempt_id",
        table_name="attempt_alerts",
    )
    op.drop_table("attempt_alerts")
    op.drop_table("attempt_lie_results")
    op.drop_index(
        "ix_attempt_category_results_category_id",
        table_name="attempt_category_results",
    )
    op.drop_index(
        "ix_attempt_category_results_attempt_id",
        table_name="attempt_category_results",
    )
    op.drop_table("attempt_category_results")
    op.drop_index(
        "ix_attempt_questions_question_id",
        table_name="attempt_questions",
    )
    op.drop_index(
        "ix_attempt_questions_attempt_id",
        table_name="attempt_questions",
    )
    op.drop_table("attempt_questions")
    op.drop_index("ix_test_attempts_status", table_name="test_attempts")
    op.drop_index(
        "ix_test_attempts_questionnaire_id",
        table_name="test_attempts",
    )
    op.drop_index(
        "ix_test_attempts_patient_id",
        table_name="test_attempts",
    )
    op.drop_table("test_attempts")
    op.drop_index(
        "ix_test_assignments_status",
        table_name="test_assignments",
    )
    op.drop_index(
        "ix_test_assignments_questionnaire_id",
        table_name="test_assignments",
    )
    op.drop_index(
        "ix_test_assignments_patient_id",
        table_name="test_assignments",
    )
    op.drop_index(
        "ix_test_assignments_access_code",
        table_name="test_assignments",
    )
    op.drop_table("test_assignments")
    op.drop_index(
        "ix_lie_question_answer_scores_question_id",
        table_name="lie_question_answer_scores",
    )
    op.drop_table("lie_question_answer_scores")
    op.drop_index(
        "ix_category_interpretation_ranges_category_id",
        table_name="category_interpretation_ranges",
    )
    op.drop_table("category_interpretation_ranges")
    op.drop_index(
        "ix_questions_questionnaire_id",
        table_name="questions",
    )
    op.drop_index("ix_questions_category_id", table_name="questions")
    op.drop_table("questions")
    op.drop_index(
        "ix_categories_questionnaire_id",
        table_name="categories",
    )
    op.drop_table("categories")
    op.drop_index(
        "ix_questionnaires_code",
        table_name="questionnaires",
    )
    op.drop_table("questionnaires")
    op.drop_index("ix_patients_public_code", table_name="patients")
    op.drop_table("patients")
