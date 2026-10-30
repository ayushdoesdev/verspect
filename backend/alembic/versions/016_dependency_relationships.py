"""Dependency relationships (graph edges)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "016_dependency_relationships"
down_revision = "015_contact_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dependency_relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_dependency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dependencies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "child_dependency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dependencies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("edge_type", sa.String(length=64), nullable=False, server_default="depends_on"),
        sa.Column("source", sa.String(length=255), nullable=True),
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
        sa.UniqueConstraint(
            "repository_id",
            "parent_dependency_id",
            "child_dependency_id",
            "edge_type",
            name="uq_dep_rel_repo_parent_child_rel",
        ),
    )
    op.create_index(
        "ix_dependency_relationships_repository_id",
        "dependency_relationships",
        ["repository_id"],
    )
    op.create_index(
        "ix_dependency_relationships_parent_dependency_id",
        "dependency_relationships",
        ["parent_dependency_id"],
    )
    op.create_index(
        "ix_dependency_relationships_child_dependency_id",
        "dependency_relationships",
        ["child_dependency_id"],
    )


def downgrade() -> None:
    op.drop_table("dependency_relationships")
