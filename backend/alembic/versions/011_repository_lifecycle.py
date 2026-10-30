"""Repository archive flags + organization audit log."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "011_repository_lifecycle"
down_revision = "010_repository_classification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "repositories",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_repositories_is_archived", "repositories", ["is_archived"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("action", sa.String(length=64), nullable=False, index=True),
        sa.Column("resource_type", sa.String(length=64), nullable=False, index=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True, index=True),
        sa.Column("resource_name", sa.String(length=512), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_index("ix_repositories_is_archived", table_name="repositories")
    op.drop_column("repositories", "archived_at")
    op.drop_column("repositories", "is_archived")
