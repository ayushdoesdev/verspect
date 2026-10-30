"""Persisted upgrade impact findings."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "017_upgrade_findings"
down_revision = "016_dependency_relationships"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "upgrade_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "simulation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("upgrade_simulations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "dependency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dependencies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("package_name", sa.String(length=255), nullable=False),
        sa.Column("current_version", sa.String(length=64), nullable=False),
        sa.Column("target_version", sa.String(length=64), nullable=False),
        sa.Column("change_type", sa.String(length=64), nullable=False),
        sa.Column("affected_api", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("affected_files", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("analysis_source", sa.String(length=32), nullable=False, server_default="deterministic"),
        sa.Column("official_reference", sa.Text(), nullable=True),
        sa.Column("is_breaking", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
    op.create_index("ix_upgrade_findings_simulation_id", "upgrade_findings", ["simulation_id"])
    op.create_index("ix_upgrade_findings_dependency_id", "upgrade_findings", ["dependency_id"])
    op.create_index("ix_upgrade_findings_repository_id", "upgrade_findings", ["repository_id"])
    op.create_index("ix_upgrade_findings_package_name", "upgrade_findings", ["package_name"])
    op.create_index("ix_upgrade_findings_change_type", "upgrade_findings", ["change_type"])
    op.create_index("ix_upgrade_findings_is_breaking", "upgrade_findings", ["is_breaking"])


def downgrade() -> None:
    op.drop_table("upgrade_findings")
