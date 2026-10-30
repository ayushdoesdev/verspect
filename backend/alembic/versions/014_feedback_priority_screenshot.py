"""Add priority and screenshot path to feedback submissions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "014_feedback_priority_screenshot"
down_revision = "013_feedback_submissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "feedback_submissions",
        sa.Column(
            "priority",
            sa.String(length=16),
            nullable=False,
            server_default="medium",
        ),
    )
    op.add_column(
        "feedback_submissions",
        sa.Column("screenshot_path", sa.String(length=1024), nullable=True),
    )
    op.create_index(
        "ix_feedback_submissions_priority",
        "feedback_submissions",
        ["priority"],
    )


def downgrade() -> None:
    op.drop_index("ix_feedback_submissions_priority", table_name="feedback_submissions")
    op.drop_column("feedback_submissions", "screenshot_path")
    op.drop_column("feedback_submissions", "priority")
