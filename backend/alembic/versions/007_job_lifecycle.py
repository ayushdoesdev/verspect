"""Worker lifecycle columns for scans and upgrade simulations.

Adds heartbeat, retry, worker attribution, queue timing and stage timings so the
background job pipeline can detect stalled/dead jobs and report observability data.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "007_job_lifecycle"
down_revision = "006_feature_usage_metrics"
branch_labels = None
depends_on = None


_TABLES = ("scans", "upgrade_simulations")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(
            table, sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True)
        )
        op.add_column(table, sa.Column("worker_name", sa.String(length=255), nullable=True))
        op.add_column(
            table,
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        )
        op.add_column(
            table,
            sa.Column(
                "cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
        )
        op.add_column(
            table,
            sa.Column("stage_timings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
        op.create_index(
            f"ix_{table}_last_heartbeat_at", table, ["last_heartbeat_at"], unique=False
        )

    # Backfill queued_at so existing rows have a queue reference point.
    op.execute("UPDATE scans SET queued_at = created_at WHERE queued_at IS NULL")
    op.execute(
        "UPDATE upgrade_simulations SET queued_at = created_at WHERE queued_at IS NULL"
    )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_index(f"ix_{table}_last_heartbeat_at", table_name=table)
        op.drop_column(table, "stage_timings")
        op.drop_column(table, "cancel_requested")
        op.drop_column(table, "retry_count")
        op.drop_column(table, "worker_name")
        op.drop_column(table, "last_heartbeat_at")
        op.drop_column(table, "queued_at")
