"""Add repository language classification fields."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "010_repository_classification"
down_revision = "009_billing_multi_provider"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column("detected_language", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("detected_language_id", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("detected_framework", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("package_manager", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("support_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column(
            "classification",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_repositories_detected_language_id",
        "repositories",
        ["detected_language_id"],
    )
    op.create_index(
        "ix_repositories_support_status",
        "repositories",
        ["support_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_repositories_support_status", table_name="repositories")
    op.drop_index("ix_repositories_detected_language_id", table_name="repositories")
    op.drop_column("repositories", "classification")
    op.drop_column("repositories", "support_status")
    op.drop_column("repositories", "package_manager")
    op.drop_column("repositories", "detected_framework")
    op.drop_column("repositories", "detected_language_id")
    op.drop_column("repositories", "detected_language")
