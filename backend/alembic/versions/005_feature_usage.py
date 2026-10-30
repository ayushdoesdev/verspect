"""Feature usage events for AI Migration Assistant metering."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "005_feature_usage"
down_revision = "004_saas_foundations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feature_usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("feature", sa.String(64), nullable=False),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "dependency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dependencies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "simulation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("upgrade_simulations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("month_key", sa.String(7), nullable=False),
        sa.Column("extra_metadata", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_feature_usage_events_organization_id", "feature_usage_events", ["organization_id"])
    op.create_index("ix_feature_usage_events_user_id", "feature_usage_events", ["user_id"])
    op.create_index("ix_feature_usage_events_feature", "feature_usage_events", ["feature"])
    op.create_index("ix_feature_usage_events_repository_id", "feature_usage_events", ["repository_id"])
    op.create_index("ix_feature_usage_events_dependency_id", "feature_usage_events", ["dependency_id"])
    op.create_index("ix_feature_usage_events_simulation_id", "feature_usage_events", ["simulation_id"])
    op.create_index("ix_feature_usage_events_month_key", "feature_usage_events", ["month_key"])
    op.create_index(
        "ix_feature_usage_org_feature_month",
        "feature_usage_events",
        ["organization_id", "feature", "month_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_feature_usage_org_feature_month", table_name="feature_usage_events")
    op.drop_index("ix_feature_usage_events_month_key", table_name="feature_usage_events")
    op.drop_index("ix_feature_usage_events_simulation_id", table_name="feature_usage_events")
    op.drop_index("ix_feature_usage_events_dependency_id", table_name="feature_usage_events")
    op.drop_index("ix_feature_usage_events_repository_id", table_name="feature_usage_events")
    op.drop_index("ix_feature_usage_events_feature", table_name="feature_usage_events")
    op.drop_index("ix_feature_usage_events_user_id", table_name="feature_usage_events")
    op.drop_index("ix_feature_usage_events_organization_id", table_name="feature_usage_events")
    op.drop_table("feature_usage_events")
