"""Configure questionnaire scoring from the exported questionnaire data.

Revision ID: 20260806_0002
Revises: 20260725_0001
Create Date: 2026-08-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260806_0002"
down_revision: str | None = "20260725_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TARGET_CODE = "psychological_profile_v1"

# Source: exports/questionnaires/questions.csv (questionnaire code ``v1``).
# Keeping the data in the migration makes it independent of seed order and of
# the temporary source questionnaire being present in a particular database.
DIRECT_POSITIONS = (
    1, 2, 3, 4, 5, 8, 9, 10,
    18, 19, 20, 21, 22, 23, 24, 25,
    28, 29, 30, 31, 32, 33, 34, 35,
    38, 39, 40, 41, 42, 43, 44, 45,
    48, 49, 50, 51, 52, 53, 54, 55,
    58, 59, 60, 61, 62, 63, 64, 65,
    68, 69, 70, 71, 72, 73, 74, 75,
    78, 79, 80, 81, 82, 83, 84, 85, 88, 89, 90,
)
REVERSE_POSITIONS = (11, 12, 13, 14, 15)
LIE_POSITIONS = (6, 7, 16, 17, 26, 27, 36, 37, 46, 47, 56, 57, 66, 67, 76, 77, 86, 87)
LIE_ANSWER_POINTS = ((1, 0), (2, 0), (3, 1), (4, 1), (5, 2))


def upgrade() -> None:
    connection = op.get_bind()
    questionnaire_id = connection.execute(
        sa.text("SELECT id FROM questionnaires WHERE code = :code"),
        {"code": TARGET_CODE},
    ).scalar_one_or_none()

    # The questionnaire is application seed data, not schema data. A fresh
    # Alembic upgrade can therefore legitimately run before it is inserted.
    if questionnaire_id is None:
        return

    questions = connection.execute(
        sa.text(
            """
            SELECT position, is_lie_question
            FROM questions
            WHERE questionnaire_id = :questionnaire_id
            """,
        ),
        {"questionnaire_id": questionnaire_id},
    ).all()
    actual = {(row.position, row.is_lie_question) for row in questions}
    expected = {
        *((position, False) for position in DIRECT_POSITIONS),
        *((position, False) for position in REVERSE_POSITIONS),
        *((position, True) for position in LIE_POSITIONS),
    }
    if actual != expected:
        raise RuntimeError(
            "Target questionnaire does not match the 90-question export",
        )

    connection.execute(
        sa.text(
            """
            UPDATE questions
            SET scoring_direction = CASE
                    WHEN position IN :direct_positions THEN 'direct'
                    WHEN position IN :reverse_positions THEN 'reverse'
                    ELSE 'none'
                END,
                weight = CASE WHEN position IN :lie_positions THEN 0 ELSE 1 END
            WHERE questionnaire_id = :questionnaire_id
            """,
        ).bindparams(
            sa.bindparam("direct_positions", expanding=True),
            sa.bindparam("reverse_positions", expanding=True),
            sa.bindparam("lie_positions", expanding=True),
        ),
        {
            "questionnaire_id": questionnaire_id,
            "direct_positions": DIRECT_POSITIONS,
            "reverse_positions": REVERSE_POSITIONS,
            "lie_positions": LIE_POSITIONS,
        },
    )

    connection.execute(
        sa.text(
            """
            INSERT INTO lie_question_answer_scores (
                id, question_id, answer_value, points
            )
            SELECT
                md5(question.id::text || ':' || score.answer_value)::uuid,
                question.id,
                score.answer_value,
                score.points
            FROM questions AS question
            CROSS JOIN (VALUES
                (1, 0), (2, 0), (3, 1), (4, 1), (5, 2)
            ) AS score(answer_value, points)
            WHERE question.questionnaire_id = :questionnaire_id
              AND question.position IN :lie_positions
            ON CONFLICT (question_id, answer_value)
            DO UPDATE SET points = EXCLUDED.points
            """,
        ).bindparams(sa.bindparam("lie_positions", expanding=True)),
        {
            "questionnaire_id": questionnaire_id,
            "lie_positions": LIE_POSITIONS,
        },
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            DELETE FROM lie_question_answer_scores
            WHERE question_id IN (
                SELECT question.id
                FROM questions AS question
                JOIN questionnaires AS questionnaire
                  ON questionnaire.id = question.questionnaire_id
                WHERE questionnaire.code = :code
            )
            """,
        ),
        {"code": TARGET_CODE},
    )
    connection.execute(
        sa.text(
            """
            UPDATE questions
            SET scoring_direction = CASE
                    WHEN is_lie_question THEN 'none'
                    ELSE NULL
                END,
                weight = CASE WHEN is_lie_question THEN 0 ELSE 1 END
            WHERE questionnaire_id = (
                SELECT id FROM questionnaires WHERE code = :code
            )
            """,
        ),
        {"code": TARGET_CODE},
    )
