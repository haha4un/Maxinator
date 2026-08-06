"""Copy scoring rules to the legacy identical questionnaire.

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


SOURCE_CODE = "v1"
TARGET_CODE = "psychological_profile_v1"


def upgrade() -> None:
    connection = op.get_bind()
    params = {"source_code": SOURCE_CODE, "target_code": TARGET_CODE}

    questionnaire_counts = connection.execute(
        sa.text(
            """
            SELECT
                count(*) FILTER (WHERE code = :source_code) AS source_count,
                count(*) FILTER (WHERE code = :target_code) AS target_count
            FROM questionnaires
            WHERE code IN (:source_code, :target_code)
            """,
        ),
        params,
    ).one()
    if questionnaire_counts != (1, 1):
        raise RuntimeError(
            "Both source and target questionnaires must exist exactly once",
        )

    question_counts = connection.execute(
        sa.text(
            """
            SELECT
                count(*) FILTER (WHERE questionnaire_id = source.id),
                count(*) FILTER (WHERE questionnaire_id = target.id)
            FROM questions
            CROSS JOIN (
                SELECT id FROM questionnaires WHERE code = :source_code
            ) AS source
            CROSS JOIN (
                SELECT id FROM questionnaires WHERE code = :target_code
            ) AS target
            WHERE questionnaire_id IN (source.id, target.id)
            """,
        ),
        params,
    ).one()
    if question_counts[0] == 0 or question_counts[0] != question_counts[1]:
        raise RuntimeError("Questionnaires do not have matching question counts")

    mismatched_questions = connection.execute(
        sa.text(
            """
            SELECT count(*)
            FROM questions AS target_question
            JOIN questionnaires AS target_questionnaire
              ON target_questionnaire.id = target_question.questionnaire_id
            LEFT JOIN questions AS source_question
              ON source_question.position = target_question.position
             AND source_question.is_lie_question = target_question.is_lie_question
             AND source_question.questionnaire_id = (
                 SELECT id FROM questionnaires WHERE code = :source_code
             )
            WHERE target_questionnaire.code = :target_code
              AND source_question.id IS NULL
            """,
        ),
        params,
    ).scalar_one()
    if mismatched_questions:
        raise RuntimeError(
            "Questionnaires do not match by question position and type",
        )

    incomplete_source_rules = connection.execute(
        sa.text(
            """
            SELECT count(*)
            FROM questions AS question
            JOIN questionnaires AS questionnaire
              ON questionnaire.id = question.questionnaire_id
            WHERE questionnaire.code = :source_code
              AND (
                  (NOT question.is_lie_question
                   AND question.scoring_direction IS NULL)
                  OR
                  (question.is_lie_question AND 5 != (
                      SELECT count(*)
                      FROM lie_question_answer_scores AS rule
                      WHERE rule.question_id = question.id
                  ))
              )
            """,
        ),
        params,
    ).scalar_one()
    if incomplete_source_rules:
        raise RuntimeError("Source questionnaire scoring is not fully configured")

    connection.execute(
        sa.text(
            """
            UPDATE questions AS target_question
            SET scoring_direction = source_question.scoring_direction,
                weight = source_question.weight
            FROM questions AS source_question,
                 questionnaires AS source_questionnaire,
                 questionnaires AS target_questionnaire
            WHERE source_question.questionnaire_id = source_questionnaire.id
              AND target_question.questionnaire_id = target_questionnaire.id
              AND source_questionnaire.code = :source_code
              AND target_questionnaire.code = :target_code
              AND source_question.position = target_question.position
            """,
        ),
        params,
    )

    connection.execute(
        sa.text(
            """
            INSERT INTO lie_question_answer_scores (
                id, question_id, answer_value, points
            )
            SELECT
                md5(target_question.id::text || ':' || rule.answer_value)::uuid,
                target_question.id,
                rule.answer_value,
                rule.points
            FROM lie_question_answer_scores AS rule
            JOIN questions AS source_question
              ON source_question.id = rule.question_id
            JOIN questionnaires AS source_questionnaire
              ON source_questionnaire.id = source_question.questionnaire_id
            JOIN questionnaires AS target_questionnaire
              ON target_questionnaire.code = :target_code
            JOIN questions AS target_question
              ON target_question.questionnaire_id = target_questionnaire.id
             AND target_question.position = source_question.position
            WHERE source_questionnaire.code = :source_code
            ON CONFLICT (question_id, answer_value)
            DO UPDATE SET points = EXCLUDED.points
            """,
        ),
        params,
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            DELETE FROM lie_question_answer_scores
            WHERE question_id IN (
                SELECT questions.id
                FROM questions
                JOIN questionnaires
                  ON questionnaires.id = questions.questionnaire_id
                WHERE questionnaires.code = :target_code
            )
            """,
        ),
        {"target_code": TARGET_CODE},
    )
    connection.execute(
        sa.text(
            """
            UPDATE questions
            SET scoring_direction = NULL,
                weight = 1
            WHERE questionnaire_id = (
                SELECT id FROM questionnaires WHERE code = :target_code
            )
              AND is_lie_question = false
            """,
        ),
        {"target_code": TARGET_CODE},
    )
