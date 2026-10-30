"""Feedback submissions for Private Beta."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "013_feedback_submissions"
down_revision = "012_subscription_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("repository", sa.String(length=512), nullable=True),
        sa.Column("page_url", sa.String(length=1024), nullable=True),
        sa.Column("app_version", sa.String(length=64), nullable=True),
        sa.Column("browser", sa.String(length=512), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_feedback_submissions_category", "feedback_submissions", ["category"])
    op.create_index("ix_feedback_submissions_email", "feedback_submissions", ["email"])
    op.create_index("ix_feedback_submissions_status", "feedback_submissions", ["status"])
    op.create_index("ix_feedback_submissions_user_id", "feedback_submissions", ["user_id"])
    op.create_index(
        "ix_feedback_submissions_created_at",
        "feedback_submissions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_feedback_submissions_created_at", table_name="feedback_submissions")
    op.drop_index("ix_feedback_submissions_user_id", table_name="feedback_submissions")
    op.drop_index("ix_feedback_submissions_status", table_name="feedback_submissions")
    op.drop_index("ix_feedback_submissions_email", table_name="feedback_submissions")
    op.drop_index("ix_feedback_submissions_category", table_name="feedback_submissions")
    op.drop_table("feedback_submissions")
