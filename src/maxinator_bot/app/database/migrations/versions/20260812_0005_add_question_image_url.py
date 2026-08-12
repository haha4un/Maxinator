"""Add an optional image URL to questions.

Revision ID: 20260812_0005
Revises: 20260806_0004
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_0005"
down_revision: str | None = "20260806_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("questions", "image_url")
