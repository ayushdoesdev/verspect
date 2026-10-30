"""Include match_kind in migration rule identity.

Fixes UniqueViolation when catalog rules share (symbol, kind) but differ by
match_kind (e.g. BaseModel import vs inheritance).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "008_migration_rule_match_kind"
down_revision = "007_job_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "migration_rules",
        sa.Column(
            "match_kind",
            sa.String(length=64),
            nullable=False,
            server_default="",
        ),
    )
    # Backfill from JSON metadata when present
    op.execute(
        sa.text(
            """
            UPDATE migration_rules
            SET match_kind = COALESCE(extra_metadata->>'match_kind', '')
            WHERE COALESCE(extra_metadata->>'match_kind', '') <> ''
            """
        )
    )
    op.drop_constraint("uq_migration_rules_identity", "migration_rules", type_="unique")
    op.create_unique_constraint(
        "uq_migration_rules_identity",
        "migration_rules",
        [
            "normalized_name",
            "from_version",
            "to_version",
            "symbol",
            "kind",
            "match_kind",
        ],
    )
    op.create_index("ix_migration_rules_match_kind", "migration_rules", ["match_kind"])


def downgrade() -> None:
    op.drop_index("ix_migration_rules_match_kind", table_name="migration_rules")
    op.drop_constraint("uq_migration_rules_identity", "migration_rules", type_="unique")
    # Collapse duplicates before restoring the old identity (keep earliest row)
    op.execute(
        sa.text(
            """
            DELETE FROM migration_rules a
            USING migration_rules b
            WHERE a.normalized_name = b.normalized_name
              AND a.from_version = b.from_version
              AND a.to_version = b.to_version
              AND a.symbol = b.symbol
              AND a.kind = b.kind
              AND a.created_at > b.created_at
            """
        )
    )
    op.create_unique_constraint(
        "uq_migration_rules_identity",
        "migration_rules",
        ["normalized_name", "from_version", "to_version", "symbol", "kind"],
    )
    op.drop_column("migration_rules", "match_kind")
