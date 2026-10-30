"""Repository schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import IDSchema, TimestampSchema
from app.scanners.language_support import (
    canonicalize_support,
    display_name_for_language,
    normalize_language_id,
)


class RepositoryImportRequest(BaseModel):
    github_repo_ids: List[int] = Field(..., min_length=1, max_length=50)
    install_webhooks: bool = True
    trigger_scan: bool = True


class RepositoryUpdateRequest(BaseModel):
    is_watching: Optional[bool] = None
    is_archived: Optional[bool] = None


class RepositoryResponse(IDSchema, TimestampSchema):
    owner_id: UUID
    github_repo_id: int
    full_name: str
    name: str
    owner_login: str
    description: Optional[str] = None
    html_url: str
    clone_url: str
    default_branch: str
    language: Optional[str] = None
    # Classifier (pipeline routing) — authoritative over GitHub `language`
    detected_language: Optional[str] = None
    detected_language_id: Optional[str] = None
    detected_framework: Optional[str] = None
    package_manager: Optional[str] = None
    support_status: Optional[str] = None
    support_label: Optional[str] = None
    classification: Optional[dict] = None
    is_private: bool
    is_fork: bool
    stars_count: int
    forks_count: int
    open_issues_count: int
    is_watching: bool
    is_archived: bool = False
    archived_at: Optional[datetime] = None
    webhook_active: bool
    sync_status: str
    last_synced_at: Optional[datetime] = None
    last_commit_sha: Optional[str] = None
    dependency_count: int
    outdated_count: int
    vulnerable_count: int
    critical_alert_count: int
    warning_count: int
    health_score: Optional[float] = None
    license_issues_count: int
    topics: Optional[list] = None

    @model_validator(mode="after")
    def derive_support_label(self) -> "RepositoryResponse":
        status, label = canonicalize_support(
            language_id=self.detected_language_id,
            support_status=self.support_status,
            support_label=self.support_label,
        )
        self.support_status = status
        self.support_label = label
        lang = normalize_language_id(self.detected_language_id)
        if lang and lang != "unknown":
            self.detected_language = display_name_for_language(
                lang, fallback=self.detected_language
            )
            if isinstance(self.classification, dict):
                blob = dict(self.classification)
                blob["support_status"] = status
                blob["support_label"] = label
                blob["language"] = self.detected_language
                self.classification = blob
        return self


class GitHubRepoListItem(BaseModel):
    github_repo_id: int
    full_name: str
    name: str
    owner_login: str
    description: Optional[str] = None
    html_url: str
    language: Optional[str] = None
    is_private: bool
    is_fork: bool
    stars_count: int
    default_branch: str
    already_imported: bool = False


class RepositoryListFilters(BaseModel):
    search: Optional[str] = None
    language: Optional[str] = None
    is_watching: Optional[bool] = None
    has_vulnerabilities: Optional[bool] = None
    has_outdated: Optional[bool] = None
