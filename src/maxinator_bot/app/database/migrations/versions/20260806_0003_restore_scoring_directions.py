"""Restore scoring directions after the legacy seed overwrote them.

Revision ID: 20260806_0003
Revises: 20260806_0002
Create Date: 2026-08-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260806_0003"
down_revision: str | None = "20260806_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SOURCE_CODE = "v1"
TARGET_CODE = "psychological_profile_v1"


def upgrade() -> None:
    result = op.get_bind().execute(
        sa.text(
            """
            UPDATE questions AS target_question
            SET scoring_direction = source_question.scoring_direction,
                weight = source_question.weight
            FROM questions AS source_question
            JOIN questionnaires AS source_questionnaire
              ON source_questionnaire.id = source_question.questionnaire_id,
                 questionnaires AS target_questionnaire
            WHERE target_question.questionnaire_id = target_questionnaire.id
              AND source_questionnaire.code = :source_code
              AND target_questionnaire.code = :target_code
              AND source_question.position = target_question.position
              AND source_question.is_lie_question
                  = target_question.is_lie_question
              AND source_question.scoring_direction IS NOT NULL
            """,
        ),
        {"source_code": SOURCE_CODE, "target_code": TARGET_CODE},
    )
    if result.rowcount != 90:
        raise RuntimeError(
            f"Expected to update 90 scoring directions, updated {result.rowcount}",
        )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """
            UPDATE questions
            SET scoring_direction = NULL
            WHERE questionnaire_id = (
                SELECT id FROM questionnaires WHERE code = :target_code
            )
              AND is_lie_question = false
            """,
        ),
        {"target_code": TARGET_CODE},
    )
