"""Initial schema — all Dependency Intelligence tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-07-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("github_id", sa.Integer(), nullable=False),
        sa.Column("github_login", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("github_access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("github_token_scopes", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email_notifications", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("slack_notifications", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("slack_webhook_url", sa.Text(), nullable=True),
        sa.Column("notify_on_critical_cve", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_on_major_release", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_on_license_violation", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("license_policy_override", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("github_id", name=op.f("uq_users_github_id")),
        sa.UniqueConstraint("github_login", name=op.f("uq_users_github_login")),
    )
    op.create_index(op.f("ix_users_github_id"), "users", ["github_id"], unique=False)
    op.create_index(op.f("ix_users_github_login"), "users", ["github_login"], unique=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)

    op.create_table(
        "repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("github_repo_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.String(length=512), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("owner_login", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("html_url", sa.Text(), nullable=False),
        sa.Column("clone_url", sa.Text(), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=False, server_default="main"),
        sa.Column("language", sa.String(length=64), nullable=True),
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_fork", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("stars_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("forks_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("open_issues_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_watching", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("webhook_id", sa.BigInteger(), nullable=True),
        sa.Column("webhook_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sync_status", sa.String(length=32), nullable=False, server_default="never_synced"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_commit_sha", sa.String(length=64), nullable=True),
        sa.Column("last_scan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dependency_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outdated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vulnerable_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("critical_alert_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("health_score", sa.Float(), nullable=True),
        sa.Column("license_issues_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("topics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_repositories_owner_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repositories")),
        sa.UniqueConstraint("owner_id", "github_repo_id", name="uq_repositories_owner_github"),
    )
    op.create_index(op.f("ix_repositories_owner_id"), "repositories", ["owner_id"], unique=False)
    op.create_index(op.f("ix_repositories_github_repo_id"), "repositories", ["github_repo_id"], unique=False)
    op.create_index(op.f("ix_repositories_full_name"), "repositories", ["full_name"], unique=False)
    op.create_index(op.f("ix_repositories_sync_status"), "repositories", ["sync_status"], unique=False)

    op.create_table(
        "dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("package_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("ecosystem", sa.String(length=64), nullable=False, server_default="PyPI"),
        sa.Column("manifest_source", sa.String(length=255), nullable=True),
        sa.Column("is_direct", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_dev", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("current_version", sa.String(length=64), nullable=True),
        sa.Column("latest_version", sa.String(length=64), nullable=True),
        sa.Column("version_constraint", sa.String(length=255), nullable=True),
        sa.Column("is_outdated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("major_behind", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("minor_behind", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("patch_behind", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("license_spdx", sa.String(length=128), nullable=True),
        sa.Column("license_raw", sa.Text(), nullable=True),
        sa.Column("license_policy_action", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("health_score", sa.Float(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_vulnerabilities", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("vulnerability_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("critical_vuln_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pypi_url", sa.Text(), nullable=True),
        sa.Column("home_page", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("requires_python", sa.String(length=64), nullable=True),
        sa.Column("download_count_month", sa.Integer(), nullable=True),
        sa.Column("github_stars", sa.Integer(), nullable=True),
        sa.Column("github_repo_url", sa.Text(), nullable=True),
        sa.Column("last_release_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_commit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("open_issues", sa.Integer(), nullable=True),
        sa.Column("release_frequency_days", sa.Float(), nullable=True),
        sa.Column("ai_explanation", sa.Text(), nullable=True),
        sa.Column("ai_should_update", sa.Text(), nullable=True),
        sa.Column("ai_security_summary", sa.Text(), nullable=True),
        sa.Column("ai_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], name=op.f("fk_dependencies_repository_id_repositories"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dependencies")),
        sa.UniqueConstraint("repository_id", "package_name", "ecosystem", name="uq_dependencies_repo_package_eco"),
    )
    op.create_index(op.f("ix_dependencies_repository_id"), "dependencies", ["repository_id"], unique=False)
    op.create_index(op.f("ix_dependencies_package_name"), "dependencies", ["package_name"], unique=False)
    op.create_index(op.f("ix_dependencies_normalized_name"), "dependencies", ["normalized_name"], unique=False)
    op.create_index(op.f("ix_dependencies_license_spdx"), "dependencies", ["license_spdx"], unique=False)
    op.create_index(op.f("ix_dependencies_status"), "dependencies", ["status"], unique=False)

    op.create_table(
        "scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("triggered_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scan_type", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="pending"),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("previous_commit_sha", sa.String(length=64), nullable=True),
        sa.Column("branch", sa.String(length=255), nullable=True),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("dependencies_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("usages_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vulnerabilities_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alerts_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("files_parsed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outdated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("license_issues", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_traceback", sa.Text(), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_stage", sa.String(length=64), nullable=True),
        sa.Column("manifest_files", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], name=op.f("fk_scans_repository_id_repositories"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], name=op.f("fk_scans_triggered_by_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scans")),
    )
    op.create_index(op.f("ix_scans_repository_id"), "scans", ["repository_id"], unique=False)
    op.create_index(op.f("ix_scans_triggered_by_user_id"), "scans", ["triggered_by_user_id"], unique=False)
    op.create_index(op.f("ix_scans_scan_type"), "scans", ["scan_type"], unique=False)
    op.create_index(op.f("ix_scans_status"), "scans", ["status"], unique=False)
    op.create_index(op.f("ix_scans_celery_task_id"), "scans", ["celery_task_id"], unique=False)

    op.create_table(
        "dependency_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dependency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_yanked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requires_python", sa.String(length=64), nullable=True),
        sa.Column("yanked_reason", sa.Text(), nullable=True),
        sa.Column("download_url", sa.Text(), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=128), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["dependency_id"], ["dependencies.id"], name=op.f("fk_dependency_versions_dependency_id_dependencies"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dependency_versions")),
        sa.UniqueConstraint("dependency_id", "version", name="uq_dependency_versions_dep_version"),
    )
    op.create_index(op.f("ix_dependency_versions_dependency_id"), "dependency_versions", ["dependency_id"], unique=False)
    op.create_index(op.f("ix_dependency_versions_version"), "dependency_versions", ["version"], unique=False)

    op.create_table(
        "library_usages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dependency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("package_name", sa.String(length=255), nullable=False),
        sa.Column("module_path", sa.String(length=512), nullable=True),
        sa.Column("symbol", sa.String(length=512), nullable=False),
        sa.Column("fully_qualified_name", sa.String(length=1024), nullable=False),
        sa.Column("usage_kind", sa.String(length=64), nullable=False, server_default="import"),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("line", sa.Integer(), nullable=False),
        sa.Column("column", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("end_line", sa.Integer(), nullable=True),
        sa.Column("end_column", sa.Integer(), nullable=True),
        sa.Column("enclosing_function", sa.String(length=255), nullable=True),
        sa.Column("enclosing_class", sa.String(length=255), nullable=True),
        sa.Column("code_snippet", sa.Text(), nullable=True),
        sa.Column("alias", sa.String(length=255), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["dependency_id"], ["dependencies.id"], name=op.f("fk_library_usages_dependency_id_dependencies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], name=op.f("fk_library_usages_repository_id_repositories"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_library_usages")),
        sa.UniqueConstraint(
            "dependency_id", "file_path", "line", "column", "symbol", "usage_kind",
            name="uq_library_usages_location",
        ),
    )
    op.create_index(op.f("ix_library_usages_dependency_id"), "library_usages", ["dependency_id"], unique=False)
    op.create_index(op.f("ix_library_usages_repository_id"), "library_usages", ["repository_id"], unique=False)
    op.create_index(op.f("ix_library_usages_package_name"), "library_usages", ["package_name"], unique=False)
    op.create_index(op.f("ix_library_usages_symbol"), "library_usages", ["symbol"], unique=False)
    op.create_index(op.f("ix_library_usages_fully_qualified_name"), "library_usages", ["fully_qualified_name"], unique=False)
    op.create_index(op.f("ix_library_usages_usage_kind"), "library_usages", ["usage_kind"], unique=False)
    op.create_index(op.f("ix_library_usages_file_path"), "library_usages", ["file_path"], unique=False)
    op.create_index(op.f("ix_library_usages_enclosing_function"), "library_usages", ["enclosing_function"], unique=False)
    op.create_index(op.f("ix_library_usages_enclosing_class"), "library_usages", ["enclosing_class"], unique=False)

    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dependency_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="info"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("affected_files", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_alerts_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], name=op.f("fk_alerts_repository_id_repositories"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dependency_id"], ["dependencies.id"], name=op.f("fk_alerts_dependency_id_dependencies"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
    )
    op.create_index(op.f("ix_alerts_user_id"), "alerts", ["user_id"], unique=False)
    op.create_index(op.f("ix_alerts_repository_id"), "alerts", ["repository_id"], unique=False)
    op.create_index(op.f("ix_alerts_dependency_id"), "alerts", ["dependency_id"], unique=False)
    op.create_index(op.f("ix_alerts_alert_type"), "alerts", ["alert_type"], unique=False)
    op.create_index(op.f("ix_alerts_severity"), "alerts", ["severity"], unique=False)
    op.create_index(op.f("ix_alerts_status"), "alerts", ["status"], unique=False)
    op.create_index(op.f("ix_alerts_fingerprint"), "alerts", ["fingerprint"], unique=False)

    op.create_table(
        "releases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dependency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("package_name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("previous_version", sa.String(length=64), nullable=True),
        sa.Column("is_major", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_minor", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_patch", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_notes_raw", sa.Text(), nullable=True),
        sa.Column("release_notes_url", sa.Text(), nullable=True),
        sa.Column("changelog_url", sa.Text(), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("breaking_changes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("deprecated_apis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_features", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("bug_fixes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("migration_difficulty", sa.String(length=32), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("affected_symbols", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("affected_files_in_repo", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ai_analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("has_breaking_changes", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["dependency_id"], ["dependencies.id"], name=op.f("fk_releases_dependency_id_dependencies"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_releases")),
        sa.UniqueConstraint("dependency_id", "version", name="uq_releases_dep_version"),
    )
    op.create_index(op.f("ix_releases_dependency_id"), "releases", ["dependency_id"], unique=False)
    op.create_index(op.f("ix_releases_package_name"), "releases", ["package_name"], unique=False)
    op.create_index(op.f("ix_releases_version"), "releases", ["version"], unique=False)

    op.create_table(
        "cves",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dependency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("osv_id", sa.String(length=128), nullable=False),
        sa.Column("cve_id", sa.String(length=64), nullable=True),
        sa.Column("aliases", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("cvss_score", sa.Float(), nullable=True),
        sa.Column("cvss_vector", sa.String(length=128), nullable=True),
        sa.Column("affected_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fixed_version", sa.String(length=64), nullable=True),
        sa.Column("introduced_version", sa.String(length=64), nullable=True),
        sa.Column("is_fixable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("references", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_osv", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("package_name", sa.String(length=255), nullable=False),
        sa.Column("ecosystem", sa.String(length=64), nullable=False, server_default="PyPI"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["dependency_id"], ["dependencies.id"], name=op.f("fk_cves_dependency_id_dependencies"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cves")),
        sa.UniqueConstraint("dependency_id", "osv_id", name="uq_cves_dep_osv"),
    )
    op.create_index(op.f("ix_cves_dependency_id"), "cves", ["dependency_id"], unique=False)
    op.create_index(op.f("ix_cves_osv_id"), "cves", ["osv_id"], unique=False)
    op.create_index(op.f("ix_cves_cve_id"), "cves", ["cve_id"], unique=False)
    op.create_index(op.f("ix_cves_severity"), "cves", ["severity"], unique=False)
    op.create_index(op.f("ix_cves_package_name"), "cves", ["package_name"], unique=False)

    op.create_table(
        "migration_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dependency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_version", sa.String(length=64), nullable=False),
        sa.Column("to_version", sa.String(length=64), nullable=False),
        sa.Column("package_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default="50"),
        sa.Column("estimated_effort_hours", sa.Float(), nullable=True),
        sa.Column("breaking_changes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("api_mappings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("affected_files", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("step_by_step", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("code_examples", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("testing_checklist", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("rollback_plan", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("should_update", sa.Boolean(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_used", sa.String(length=128), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["dependency_id"], ["dependencies.id"], name=op.f("fk_migration_reports_dependency_id_dependencies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], name=op.f("fk_migration_reports_repository_id_repositories"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_migration_reports")),
    )
    op.create_index(op.f("ix_migration_reports_dependency_id"), "migration_reports", ["dependency_id"], unique=False)
    op.create_index(op.f("ix_migration_reports_repository_id"), "migration_reports", ["repository_id"], unique=False)
    op.create_index(op.f("ix_migration_reports_package_name"), "migration_reports", ["package_name"], unique=False)

    op.create_table(
        "alternative_libraries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dependency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("package_name", sa.String(length=255), nullable=False),
        sa.Column("alternative_name", sa.String(length=255), nullable=False),
        sa.Column("alternative_normalized", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("pros", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("popularity_score", sa.Float(), nullable=True),
        sa.Column("health_score", sa.Float(), nullable=True),
        sa.Column("download_count_month", sa.Integer(), nullable=True),
        sa.Column("github_stars", sa.Integer(), nullable=True),
        sa.Column("migration_effort", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("api_compatibility", sa.Float(), nullable=True),
        sa.Column("license_spdx", sa.String(length=128), nullable=True),
        sa.Column("pypi_url", sa.Text(), nullable=True),
        sa.Column("home_page", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="ai"),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["dependency_id"], ["dependencies.id"], name=op.f("fk_alternative_libraries_dependency_id_dependencies"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alternative_libraries")),
        sa.UniqueConstraint("dependency_id", "alternative_name", name="uq_alternative_libraries_dep_alt"),
    )
    op.create_index(op.f("ix_alternative_libraries_dependency_id"), "alternative_libraries", ["dependency_id"], unique=False)
    op.create_index(op.f("ix_alternative_libraries_package_name"), "alternative_libraries", ["package_name"], unique=False)
    op.create_index(op.f("ix_alternative_libraries_alternative_name"), "alternative_libraries", ["alternative_name"], unique=False)


def downgrade() -> None:
    op.drop_table("alternative_libraries")
    op.drop_table("migration_reports")
    op.drop_table("cves")
    op.drop_table("releases")
    op.drop_table("alerts")
    op.drop_table("library_usages")
    op.drop_table("dependency_versions")
    op.drop_table("scans")
    op.drop_table("dependencies")
    op.drop_table("repositories")
    op.drop_table("users")
