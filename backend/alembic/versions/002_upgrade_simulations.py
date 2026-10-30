"""Add upgrade_simulations table for AI Upgrade Impact Simulator.

Revision ID: 002_upgrade_simulations
Revises: 001_initial
Create Date: 2026-08-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_upgrade_simulations"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "upgrade_simulations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dependency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("triggered_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("package_name", sa.String(length=255), nullable=False),
        sa.Column("from_version", sa.String(length=64), nullable=False),
        sa.Column("to_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="pending"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_stage", sa.String(length=64), nullable=True),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("cache_key", sa.String(length=128), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("safe_to_upgrade", sa.Boolean(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("readiness_score", sa.Float(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("migration_time_hours", sa.Float(), nullable=True),
        sa.Column("migration_time_label", sa.String(length=128), nullable=True),
        sa.Column("breaking_apis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("deprecated_apis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("affected_files", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("affected_symbols", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("affected_functions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("affected_classes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("security_improvements", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("performance_improvements", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("manual_work_required", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("automatic_fixes_possible", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("migration_plan", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("suggested_changes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("readiness_factors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("collected_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("usage_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_ai_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model_used", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["dependency_id"],
            ["dependencies.id"],
            name=op.f("fk_upgrade_simulations_dependency_id_dependencies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_upgrade_simulations_repository_id_repositories"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by_user_id"],
            ["users.id"],
            name=op.f("fk_upgrade_simulations_triggered_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_upgrade_simulations")),
    )
    op.create_index(op.f("ix_upgrade_simulations_dependency_id"), "upgrade_simulations", ["dependency_id"])
    op.create_index(op.f("ix_upgrade_simulations_repository_id"), "upgrade_simulations", ["repository_id"])
    op.create_index(op.f("ix_upgrade_simulations_triggered_by_user_id"), "upgrade_simulations", ["triggered_by_user_id"])
    op.create_index(op.f("ix_upgrade_simulations_package_name"), "upgrade_simulations", ["package_name"])
    op.create_index(op.f("ix_upgrade_simulations_status"), "upgrade_simulations", ["status"])
    op.create_index(op.f("ix_upgrade_simulations_celery_task_id"), "upgrade_simulations", ["celery_task_id"])
    op.create_index(op.f("ix_upgrade_simulations_cache_key"), "upgrade_simulations", ["cache_key"])


def downgrade() -> None:
    op.drop_table("upgrade_simulations")
