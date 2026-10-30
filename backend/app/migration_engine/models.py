"""Pydantic / dataclass models for the Universal Migration Engine (in-memory)."""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


class RuleKind(str, Enum):
    REMOVED = "removed"
    DEPRECATED = "deprecated"
    RENAMED = "renamed"
    SIGNATURE_CHANGE = "signature_change"
    BEHAVIOR_CHANGE = "behavior_change"
    IMPORT_PATH_CHANGE = "import_path_change"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ADDED = "added"


class RuleSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class EffortLevel(str, Enum):
    TRIVIAL = "trivial"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ValidationStatus(str, Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class MigrationRuleDTO(BaseModel):
    """Universal migration rule — one schema for every library."""

    id: Optional[str] = None
    library: str
    from_version: str
    to_version: str
    symbol: str
    kind: str
    description: str
    severity: str = RuleSeverity.MEDIUM.value
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    before: Optional[str] = None
    after: Optional[str] = None
    reason: Optional[str] = None
    official_reference: Optional[str] = None
    reference_title: Optional[str] = None
    auto_fixable: bool = False
    estimated_effort: str = EffortLevel.MEDIUM.value
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    validation_status: str = ValidationStatus.PENDING.value
    # Structured match criteria
    match_kind: Optional[str] = None  # decorator | import | function_call | ...
    unchanged: bool = False  # True → "No migration required"
    import_fix: Optional[dict] = None

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: Any) -> float:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return 0.5
        if f > 1.0:
            f = f / 100.0
        return max(0.0, min(1.0, f))


class MigrationRuleBatch(BaseModel):
    """AI extraction batch — list of universal rules."""

    rules: List[MigrationRuleDTO] = Field(default_factory=list)
    summary: Optional[str] = None
    official_references: List[str] = Field(default_factory=list)


class MatchedUsage(BaseModel):
    rule: MigrationRuleDTO
    file_path: str
    line: Optional[int] = None
    column: Optional[int] = None
    symbol: str
    fully_qualified_name: str
    usage_kind: Optional[str] = None
    enclosing_function: Optional[str] = None
    enclosing_class: Optional[str] = None
    code_snippet: Optional[str] = None
    match_confidence: float = 0.7


class PatchDTO(BaseModel):
    file_path: str
    line: Optional[int] = None
    symbol: Optional[str] = None
    current_code: str
    suggested_code: str
    unified_diff: Optional[str] = None
    reason: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    official_reference: Optional[str] = None
    auto_fixable: bool = False
    rule_id: Optional[str] = None
    validation_status: str = ValidationStatus.PENDING.value
    validation_errors: List[str] = Field(default_factory=list)


class ScoringResult(BaseModel):
    readiness_score: float = Field(ge=0.0, le=100.0)
    risk_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    migration_difficulty: str = EffortLevel.MEDIUM.value
    migration_time_hours: float = 1.0
    security_improvement: float = 0.0
    performance_improvement: float = 0.0
    technical_debt_reduction: float = 0.0
    auto_fix_count: int = 0
    manual_fix_count: int = 0
    breakdown: dict = Field(default_factory=dict)


class OfficialReference(BaseModel):
    title: str
    url: str
    source_type: str = "docs"


class MigrationFinding(BaseModel):
    """Classified finding for UI — never a fake patch."""

    status: str  # automatic_migration | manual_review_required | unknown | no_migration_required
    file_path: str
    line: Optional[int] = None
    symbol: str
    usage_kind: Optional[str] = None
    current_code: Optional[str] = None
    suggested_code: Optional[str] = None
    unified_diff: Optional[str] = None
    replacement: Optional[str] = None
    confidence: float = 0.0
    reason: str = ""
    official_reference: Optional[str] = None
    reference_title: Optional[str] = None
    automatic: bool = False
    rule_id: Optional[str] = None


class UpgradeEngineReport(BaseModel):
    package_name: str
    from_version: str
    to_version: str
    summary: str
    scoring: ScoringResult
    matched_usages: List[MatchedUsage] = Field(default_factory=list)
    rules: List[MigrationRuleDTO] = Field(default_factory=list)
    patches: List[PatchDTO] = Field(default_factory=list)
    findings: List[MigrationFinding] = Field(default_factory=list)
    affected_files: List[dict] = Field(default_factory=list)
    affected_symbols: List[str] = Field(default_factory=list)
    official_references: List[str] = Field(default_factory=list)
    official_reference_items: List[OfficialReference] = Field(default_factory=list)
    migration_plan: List[dict] = Field(default_factory=list)
    security_improvements: List[str] = Field(default_factory=list)
    performance_improvements: List[str] = Field(default_factory=list)
