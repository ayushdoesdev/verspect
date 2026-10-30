"""Pending plan changes for subscription lifecycle."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "012_subscription_lifecycle"
down_revision = "011_repository_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("pending_plan", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("pending_interval", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("pending_change_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column(
            "pending_change_effective_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_subscriptions_pending_plan",
        "subscriptions",
        ["pending_plan"],
    )


def downgrade() -> None:
    op.drop_index("ix_subscriptions_pending_plan", table_name="subscriptions")
    op.drop_column("subscriptions", "pending_change_effective_at")
    op.drop_column("subscriptions", "pending_change_type")
    op.drop_column("subscriptions", "pending_interval")
    op.drop_column("subscriptions", "pending_plan")
