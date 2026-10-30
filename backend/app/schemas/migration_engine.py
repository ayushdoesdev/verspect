"""API schemas for the Universal Migration Intelligence Engine."""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import IDSchema, TimestampSchema


class MigrationRuleResponse(IDSchema, TimestampSchema):
    library: str
    normalized_name: str
    from_version: str
    to_version: str
    symbol: str
    kind: str
    description: str
    severity: str
    confidence: float
    before: Optional[str] = None
    after: Optional[str] = None
    reason: Optional[str] = None
    official_reference: Optional[str] = None
    auto_fixable: bool = False
    estimated_effort: str = "medium"
    validation_status: str = "pending"
    source_type: Optional[str] = None
    source_url: Optional[str] = None


class PatchSuggestionResponse(IDSchema, TimestampSchema):
    report_id: UUID
    rule_id: Optional[UUID] = None
    file_path: str
    line: Optional[int] = None
    symbol: Optional[str] = None
    current_code: str
    suggested_code: str
    unified_diff: Optional[str] = None
    reason: str
    confidence: float
    official_reference: Optional[str] = None
    auto_fixable: bool = False
    validation_status: str = "pending"
    validation_errors: Optional[List[Any]] = None


class MigrationEngineReportResponse(IDSchema, TimestampSchema):
    dependency_id: UUID
    repository_id: UUID
    simulation_id: Optional[UUID] = None
    package_name: str
    normalized_name: str
    from_version: str
    to_version: str
    readiness_score: float
    risk_score: float
    confidence: float
    migration_difficulty: str
    migration_time_hours: Optional[float] = None
    security_improvement: float = 0.0
    performance_improvement: float = 0.0
    technical_debt_reduction: float = 0.0
    affected_files: Optional[List[Any]] = None
    affected_symbols: Optional[List[Any]] = None
    matched_rule_ids: Optional[List[Any]] = None
    auto_fix_count: int = 0
    manual_fix_count: int = 0
    summary: Optional[str] = None
    official_references: Optional[List[Any]] = None
    scoring_breakdown: Optional[dict] = None
    patches: List[PatchSuggestionResponse] = Field(default_factory=list)


class KnowledgeBaseEntryResponse(IDSchema, TimestampSchema):
    package_name: str
    normalized_name: str
    ecosystem: str = "PyPI"
    pypi_url: Optional[str] = None
    github_url: Optional[str] = None
    docs_url: Optional[str] = None
    summary: Optional[str] = None
    rule_count: int = 0
    last_learned_at: Optional[datetime] = None
    last_release_checked: Optional[str] = None


class KnowledgeLookupResponse(BaseModel):
    entry: Optional[KnowledgeBaseEntryResponse] = None
    rules: List[MigrationRuleResponse] = Field(default_factory=list)
    release_notes_count: int = 0
    documentation_sources: List[dict] = Field(default_factory=list)


class LearnRulesRequest(BaseModel):
    package_name: str
    from_version: str
    to_version: str
    github_url: Optional[str] = None
    force_refresh: bool = False


class LearnRulesResponse(BaseModel):
    status: str
    package_name: str
    from_version: str
    to_version: str
    task_id: Optional[str] = None
    rules_count: Optional[int] = None
    message: str
