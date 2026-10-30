"""Dependency-related schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import IDSchema, TimestampSchema


class DependencyResponse(IDSchema, TimestampSchema):
    repository_id: UUID
    package_name: str
    normalized_name: str
    ecosystem: str
    manifest_source: Optional[str] = None
    is_direct: bool
    is_dev: bool
    current_version: Optional[str] = None
    latest_version: Optional[str] = None
    version_constraint: Optional[str] = None
    is_outdated: bool
    major_behind: int
    minor_behind: int
    patch_behind: int
    license_spdx: Optional[str] = None
    license_raw: Optional[str] = None
    license_policy_action: Optional[str] = None
    status: str
    health_score: Optional[float] = None
    risk_score: Optional[float] = None
    usage_count: int
    file_count: int
    has_vulnerabilities: bool
    vulnerability_count: int
    critical_vuln_count: int
    osv_status: Optional[str] = None
    pypi_url: Optional[str] = None
    home_page: Optional[str] = None
    summary: Optional[str] = None
    author: Optional[str] = None
    download_count_month: Optional[int] = None
    github_stars: Optional[int] = None
    github_repo_url: Optional[str] = None
    last_release_at: Optional[datetime] = None
    ai_explanation: Optional[str] = None
    ai_should_update: Optional[str] = None
    ai_security_summary: Optional[str] = None


class DependencyVersionResponse(IDSchema, TimestampSchema):
    dependency_id: UUID
    version: str
    is_current: bool
    is_latest: bool
    is_yanked: bool
    released_at: Optional[datetime] = None
    requires_python: Optional[str] = None


class LibraryUsageResponse(IDSchema, TimestampSchema):
    dependency_id: UUID
    repository_id: UUID
    package_name: str
    module_path: Optional[str] = None
    symbol: str
    fully_qualified_name: str
    usage_kind: str
    file_path: str
    line: int
    column: int
    end_line: Optional[int] = None
    enclosing_function: Optional[str] = None
    enclosing_class: Optional[str] = None
    code_snippet: Optional[str] = None
    alias: Optional[str] = None


class CVEResponse(IDSchema, TimestampSchema):
    dependency_id: UUID
    osv_id: str
    cve_id: Optional[str] = None
    aliases: Optional[list] = None
    summary: str
    details: Optional[str] = None
    severity: str
    cvss_score: Optional[float] = None
    fixed_version: Optional[str] = None
    introduced_version: Optional[str] = None
    is_fixable: bool
    published_at: Optional[datetime] = None
    package_name: str
    references: Optional[list] = None


class ReleaseResponse(IDSchema, TimestampSchema):
    dependency_id: UUID
    package_name: str
    version: str
    previous_version: Optional[str] = None
    is_major: bool
    is_minor: bool
    is_patch: bool
    released_at: Optional[datetime] = None
    ai_summary: Optional[str] = None
    breaking_changes: Optional[list] = None
    deprecated_apis: Optional[list] = None
    new_features: Optional[list] = None
    migration_difficulty: Optional[str] = None
    risk_score: Optional[float] = None
    has_breaking_changes: bool
    affected_files_in_repo: Optional[list] = None


class AlternativeLibraryResponse(IDSchema, TimestampSchema):
    dependency_id: UUID
    package_name: str
    alternative_name: str
    reason: str
    pros: Optional[list] = None
    cons: Optional[list] = None
    popularity_score: Optional[float] = None
    health_score: Optional[float] = None
    migration_effort: str
    download_count_month: Optional[int] = None
    github_stars: Optional[int] = None
    license_spdx: Optional[str] = None
    summary: Optional[str] = None
    rank: int
    confidence: Optional[float] = None


class MigrationReportResponse(IDSchema, TimestampSchema):
    dependency_id: UUID
    repository_id: UUID
    from_version: str
    to_version: str
    package_name: str
    title: str
    summary: str
    difficulty: str
    risk_score: float
    estimated_effort_hours: Optional[float] = None
    breaking_changes: Optional[list] = None
    step_by_step: Optional[list] = None
    code_examples: Optional[list] = None
    affected_files: Optional[list] = None
    recommendation: Optional[str] = None
    should_update: Optional[bool] = None
    generated_at: datetime


class DependencyDetailResponse(DependencyResponse):
    versions: List[DependencyVersionResponse] = Field(default_factory=list)
    usages: List[LibraryUsageResponse] = Field(default_factory=list)
    cves: List[CVEResponse] = Field(default_factory=list)
    releases: List[ReleaseResponse] = Field(default_factory=list)
    alternatives: List[AlternativeLibraryResponse] = Field(default_factory=list)
    migration_reports: List[MigrationReportResponse] = Field(default_factory=list)
    upgrade_advisor: Optional[dict] = None
    documentation_links: List[dict] = Field(default_factory=list)
    health_breakdown: Optional[dict] = None
    introduced_by: List[dict] = Field(default_factory=list)


def apply_osv_status(response: DependencyResponse, dep: object) -> DependencyResponse:
    """Copy persisted OSV query status off extra_metadata. Missing means not yet scanned."""
    meta = getattr(dep, "extra_metadata", None)
    if not isinstance(meta, dict):
        return response
    status = meta.get("osv_status")
    if status not in {"ok", "unavailable"}:
        return response
    return response.model_copy(update={"osv_status": status})


class DependencyListFilters(BaseModel):
    search: Optional[str] = None
    status: Optional[str] = None
    is_outdated: Optional[bool] = None
    has_vulnerabilities: Optional[bool] = None
    license_policy_action: Optional[str] = None
    repository_id: Optional[UUID] = None
    is_direct: Optional[bool] = None
