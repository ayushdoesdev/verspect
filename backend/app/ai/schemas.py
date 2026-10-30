"""Structured AI response schemas — validate JSON before returning."""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


def coerce_should_update_str(v: Any) -> str:
    """Accept bool/number from local LLMs without discarding the whole response."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "Yes — update recommended." if v else "No urgent update required."
    if isinstance(v, (int, float)):
        return str(v)
    return str(v).strip()


class UpgradeSummary(BaseModel):
    summary: str = ""
    should_update: str = ""
    readiness_score: float = Field(default=50.0, ge=0.0, le=100.0)
    risk_score: float = Field(default=50.0, ge=0.0, le=100.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    benefits: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    estimated_effort: str = "medium"
    recommended_version: Optional[str] = None

    @field_validator("should_update", mode="before")
    @classmethod
    def coerce_should_update(cls, v: Any) -> str:
        return coerce_should_update_str(v)

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_conf(cls, v: Any) -> float:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return 0.5
        if f > 1.0:
            f = f / 100.0
        return max(0.0, min(1.0, f))


class MigrationPlanPhase(BaseModel):
    phase: int = 1
    title: str = ""
    description: str = ""
    reasoning: str = ""
    difficulty: str = "medium"
    estimated_duration_hours: float = 1.0
    tasks: List[str] = Field(default_factory=list)


class MigrationPlan(BaseModel):
    title: str = ""
    summary: str = ""
    difficulty: str = "medium"
    risk_score: float = 50.0
    estimated_effort_hours: Optional[float] = None
    breaking_changes: List[Any] = Field(default_factory=list)
    api_mappings: List[Any] = Field(default_factory=list)
    affected_files: List[Any] = Field(default_factory=list)
    step_by_step: List[Any] = Field(default_factory=list)
    migration_plan: List[MigrationPlanPhase] = Field(default_factory=list)
    code_examples: List[Any] = Field(default_factory=list)
    testing_checklist: List[str] = Field(default_factory=list)
    rollback_plan: str = ""
    recommendation: str = ""
    should_update: bool = True


class DependencySummary(BaseModel):
    explanation: str = ""
    should_update: str = ""
    security_summary: str = ""
    migration_summary: str = ""
    breaking_changes_summary: str = ""

    @field_validator("should_update", mode="before")
    @classmethod
    def coerce_should_update(cls, v: Any) -> str:
        return coerce_should_update_str(v)

    @field_validator(
        "explanation",
        "security_summary",
        "migration_summary",
        "breaking_changes_summary",
        mode="before",
    )
    @classmethod
    def coerce_str_fields(cls, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, bool):
            return "yes" if v else "no"
        return str(v).strip() if not isinstance(v, str) else v


class ReleaseNotesSummary(BaseModel):
    ai_summary: str = ""
    breaking_changes: List[str] = Field(default_factory=list)
    deprecated_apis: List[str] = Field(default_factory=list)
    new_features: List[str] = Field(default_factory=list)
    bug_fixes: List[str] = Field(default_factory=list)
    migration_difficulty: str = "low"
    risk_score: float = 25.0
    affected_symbols: List[str] = Field(default_factory=list)
    has_breaking_changes: bool = False


class PatchExplanation(BaseModel):
    explanation: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    risk_notes: List[str] = Field(default_factory=list)
    testing_notes: List[str] = Field(default_factory=list)
    official_reference: Optional[str] = None


class RepositorySummary(BaseModel):
    summary: str = ""
    tech_stack: List[str] = Field(default_factory=list)
    risk_highlights: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    health_score: float = Field(default=50.0, ge=0.0, le=100.0)


class AlternativeItem(BaseModel):
    alternative_name: str = ""
    reason: str = ""
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    migration_effort: str = "medium"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class AlternativeRecommendation(BaseModel):
    alternatives: List[AlternativeItem] = Field(default_factory=list)


class SecuritySummary(BaseModel):
    summary: str = ""
    severity_overview: str = ""
    actionable_steps: List[str] = Field(default_factory=list)
    risk_score: float = Field(default=50.0, ge=0.0, le=100.0)


class MigrationSummary(BaseModel):
    summary: str = ""
    impact_explanation: str = ""
    effort_rationale: str = ""
    migration_plan: List[MigrationPlanPhase] = Field(default_factory=list)


class CompletionMeta(BaseModel):
    """Metadata returned alongside completions (logging / cache)."""

    provider: str
    model: str
    latency_ms: float = 0.0
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cache_hit: bool = False
    streamed: bool = False
