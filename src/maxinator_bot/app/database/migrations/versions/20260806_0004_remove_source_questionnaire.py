"""Remove the duplicate source questionnaire after copying its scoring.

Revision ID: 20260806_0004
Revises: 20260806_0003
Create Date: 2026-08-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260806_0004"
down_revision: str | None = "20260806_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


QUESTIONNAIRE_CODE = "v1"


def upgrade() -> None:
    connection = op.get_bind()
    params = {"code": QUESTIONNAIRE_CODE}

    # Release session references before deleting attempts and questionnaire.
    connection.execute(
        sa.text(
            """
            UPDATE bot_sessions
            SET selected_questionnaire_id = NULL
            WHERE selected_questionnaire_id IN (
                SELECT id FROM questionnaires WHERE code = :code
            )
            """,
        ),
        params,
    )
    connection.execute(
        sa.text(
            """
            UPDATE bot_sessions
            SET active_attempt_id = NULL,
                state = 'idle',
                page = NULL,
                context = NULL
            WHERE active_attempt_id IN (
                SELECT attempt.id
                FROM test_attempts AS attempt
                JOIN questionnaires AS questionnaire
                  ON questionnaire.id = attempt.questionnaire_id
                WHERE questionnaire.code = :code
            )
            """,
        ),
        params,
    )

    # Attempt result, answer and alert rows cascade from test_attempts.
    connection.execute(
        sa.text(
            """
            DELETE FROM test_attempts
            WHERE questionnaire_id IN (
                SELECT id FROM questionnaires WHERE code = :code
            )
            """,
        ),
        params,
    )
    connection.execute(
        sa.text(
            """
            DELETE FROM test_assignments
            WHERE questionnaire_id IN (
                SELECT id FROM questionnaires WHERE code = :code
            )
            """,
        ),
        params,
    )
    result = connection.execute(
        sa.text("DELETE FROM questionnaires WHERE code = :code"),
        params,
    )
    if result.rowcount not in (0, 1):
        raise RuntimeError(
            f"Expected to delete at most one questionnaire, deleted {result.rowcount}",
        )


def downgrade() -> None:
    # Questionnaire contents and patient responses cannot be restored safely.
    pass
