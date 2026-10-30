"""Universal Migration Knowledge Base tables.

Revision ID: 003_migration_kb
Revises: 002_upgrade_simulations
Create Date: 2026-08-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_migration_kb"
down_revision: Union[str, None] = "002_upgrade_simulations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_base_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("package_name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("ecosystem", sa.String(64), nullable=False, server_default="PyPI"),
        sa.Column("pypi_url", sa.Text(), nullable=True),
        sa.Column("github_url", sa.Text(), nullable=True),
        sa.Column("docs_url", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("rule_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_learned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_release_checked", sa.String(64), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_base_entries")),
        sa.UniqueConstraint("normalized_name", "ecosystem", name="uq_kb_normalized_eco"),
    )
    op.create_index("ix_knowledge_base_entries_package_name", "knowledge_base_entries", ["package_name"])
    op.create_index("ix_knowledge_base_entries_normalized_name", "knowledge_base_entries", ["normalized_name"])

    op.create_table(
        "documentation_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("content_excerpt", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_base_entries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("knowledge_base_id", "url", "source_type", name="uq_doc_sources_kb_url_type"),
    )
    op.create_index("ix_documentation_sources_knowledge_base_id", "documentation_sources", ["knowledge_base_id"])
    op.create_index("ix_documentation_sources_source_type", "documentation_sources", ["source_type"])
    op.create_index("ix_documentation_sources_content_hash", "documentation_sources", ["content_hash"])

    op.create_table(
        "knowledge_release_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("package_name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("previous_version", sa.String(64), nullable=True),
        sa.Column("source", sa.String(64), nullable=False, server_default="github"),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("breaking_hints", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("deprecated_hints", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("security_hints", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_name", "version", "source", name="uq_knowledge_release_notes_pkg_ver_src"),
    )
    op.create_index("ix_knowledge_release_notes_package_name", "knowledge_release_notes", ["package_name"])
    op.create_index("ix_knowledge_release_notes_normalized_name", "knowledge_release_notes", ["normalized_name"])
    op.create_index("ix_knowledge_release_notes_version", "knowledge_release_notes", ["version"])

    op.create_table(
        "migration_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("library", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("from_version", sa.String(64), nullable=False),
        sa.Column("to_version", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(512), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False, server_default="medium"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("before", sa.Text(), nullable=True),
        sa.Column("after", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("official_reference", sa.Text(), nullable=True),
        sa.Column("auto_fixable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("estimated_effort", sa.String(32), nullable=False, server_default="medium"),
        sa.Column("validation_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("source_type", sa.String(64), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_base_entries.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "normalized_name", "from_version", "to_version", "symbol", "kind",
            name="uq_migration_rules_identity",
        ),
    )
    op.create_index("ix_migration_rules_knowledge_base_id", "migration_rules", ["knowledge_base_id"])
    op.create_index("ix_migration_rules_library", "migration_rules", ["library"])
    op.create_index("ix_migration_rules_normalized_name", "migration_rules", ["normalized_name"])
    op.create_index("ix_migration_rules_symbol", "migration_rules", ["symbol"])
    op.create_index("ix_migration_rules_kind", "migration_rules", ["kind"])
    op.create_index("ix_migration_rules_validation_status", "migration_rules", ["validation_status"])

    op.create_table(
        "migration_examples",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("before_code", sa.Text(), nullable=False),
        sa.Column("after_code", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("language", sa.String(32), nullable=False, server_default="python"),
        sa.Column("official_reference", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["migration_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_migration_examples_rule_id", "migration_examples", ["rule_id"])

    op.create_table(
        "migration_engine_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dependency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("simulation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("package_name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("from_version", sa.String(64), nullable=False),
        sa.Column("to_version", sa.String(64), nullable=False),
        sa.Column("readiness_score", sa.Float(), nullable=False, server_default="50"),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default="50"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("migration_difficulty", sa.String(32), nullable=False, server_default="medium"),
        sa.Column("migration_time_hours", sa.Float(), nullable=True),
        sa.Column("security_improvement", sa.Float(), nullable=False, server_default="0"),
        sa.Column("performance_improvement", sa.Float(), nullable=False, server_default="0"),
        sa.Column("technical_debt_reduction", sa.Float(), nullable=False, server_default="0"),
        sa.Column("affected_files", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("affected_symbols", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("matched_rule_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("auto_fix_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("manual_fix_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("official_references", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("scoring_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["dependency_id"], ["dependencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["simulation_id"], ["upgrade_simulations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_migration_engine_reports_dependency_id", "migration_engine_reports", ["dependency_id"])
    op.create_index("ix_migration_engine_reports_repository_id", "migration_engine_reports", ["repository_id"])
    op.create_index("ix_migration_engine_reports_simulation_id", "migration_engine_reports", ["simulation_id"])
    op.create_index("ix_migration_engine_reports_package_name", "migration_engine_reports", ["package_name"])

    op.create_table(
        "patch_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("line", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(512), nullable=True),
        sa.Column("current_code", sa.Text(), nullable=False),
        sa.Column("suggested_code", sa.Text(), nullable=False),
        sa.Column("unified_diff", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("official_reference", sa.Text(), nullable=True),
        sa.Column("auto_fixable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("validation_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("validation_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["migration_engine_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["migration_rules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patch_suggestions_report_id", "patch_suggestions", ["report_id"])
    op.create_index("ix_patch_suggestions_rule_id", "patch_suggestions", ["rule_id"])
    op.create_index("ix_patch_suggestions_file_path", "patch_suggestions", ["file_path"])
    op.create_index("ix_patch_suggestions_validation_status", "patch_suggestions", ["validation_status"])

    op.create_table(
        "validation_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("validator", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_validation_history_entity_type", "validation_history", ["entity_type"])
    op.create_index("ix_validation_history_entity_id", "validation_history", ["entity_id"])


def downgrade() -> None:
    op.drop_table("validation_history")
    op.drop_table("patch_suggestions")
    op.drop_table("migration_engine_reports")
    op.drop_table("migration_examples")
    op.drop_table("migration_rules")
    op.drop_table("knowledge_release_notes")
    op.drop_table("documentation_sources")
    op.drop_table("knowledge_base_entries")
