"""Add metering columns to feature_usage_events."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "006_feature_usage_metrics"
down_revision = "005_feature_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("feature_usage_events", sa.Column("tokens_used", sa.Integer(), nullable=True))
    op.add_column(
        "feature_usage_events",
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6), nullable=True),
    )
    op.add_column(
        "feature_usage_events",
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("feature_usage_events", "execution_time_ms")
    op.drop_column("feature_usage_events", "estimated_cost_usd")
    op.drop_column("feature_usage_events", "tokens_used")
