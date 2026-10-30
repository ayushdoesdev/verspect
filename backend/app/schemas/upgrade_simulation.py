"""Pydantic schemas for AI Upgrade Impact Simulator."""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import IDSchema, TimestampSchema


# ---------------------------------------------------------------------------
# Structured AI response models (validated)
# ---------------------------------------------------------------------------


class BreakingAPIItem(BaseModel):
    symbol: str
    fully_qualified_name: str
    severity: str = Field(default="medium", pattern="^(critical|high|medium|low|info)$")
    reason: str
    replacement: Optional[str] = None
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class DeprecatedAPIItem(BaseModel):
    symbol: str
    fully_qualified_name: str
    reason: str
    replacement: Optional[str] = None
    removal_version: Optional[str] = None
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class FileImpactItem(BaseModel):
    file_path: str
    affected_apis: List[str] = Field(default_factory=list)
    reason: str
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    suggested_changes: List[str] = Field(default_factory=list)
    enclosing_functions: List[str] = Field(default_factory=list)
    enclosing_classes: List[str] = Field(default_factory=list)


class SuggestedChangeItem(BaseModel):
    file_path: str
    line: Optional[int] = None
    symbol: Optional[str] = None
    current_code: str
    suggested_code: str
    explanation: str
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    automatic: bool = False


class MigrationPhaseItem(BaseModel):
    phase: int = Field(ge=1)
    title: str
    description: str
    reasoning: str
    difficulty: str = Field(
        default="medium",
        pattern="^(trivial|low|medium|high|very_high)$",
    )
    estimated_duration_hours: float = Field(default=1.0, ge=0.0)
    tasks: List[str] = Field(default_factory=list)


class ReadinessFactors(BaseModel):
    breaking_apis: float = Field(default=50.0, ge=0.0, le=100.0)
    plugin_compatibility: float = Field(default=50.0, ge=0.0, le=100.0)
    deprecated_calls: float = Field(default=50.0, ge=0.0, le=100.0)
    security: float = Field(default=50.0, ge=0.0, le=100.0)
    tests: float = Field(default=50.0, ge=0.0, le=100.0)


class UpgradeImpactAIResult(BaseModel):
    """Validated structured output from the AI upgrade impact analyzer."""

    summary: str
    safe_to_upgrade: bool
    confidence: float = Field(ge=0.0, le=1.0)
    readiness_score: float = Field(ge=0.0, le=100.0)
    risk_score: float = Field(ge=0.0, le=100.0)
    migration_time_hours: float = Field(ge=0.0)
    migration_time_label: str

    breaking_apis: List[BreakingAPIItem] = Field(default_factory=list)
    deprecated_apis: List[DeprecatedAPIItem] = Field(default_factory=list)
    affected_files: List[FileImpactItem] = Field(default_factory=list)
    affected_symbols: List[str] = Field(default_factory=list)
    affected_functions: List[str] = Field(default_factory=list)
    affected_classes: List[str] = Field(default_factory=list)

    security_improvements: List[str] = Field(default_factory=list)
    performance_improvements: List[str] = Field(default_factory=list)
    manual_work_required: List[str] = Field(default_factory=list)
    automatic_fixes_possible: List[str] = Field(default_factory=list)

    migration_plan: List[MigrationPhaseItem] = Field(default_factory=list)
    suggested_changes: List[SuggestedChangeItem] = Field(default_factory=list)
    readiness_factors: ReadinessFactors = Field(default_factory=ReadinessFactors)

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


# ---------------------------------------------------------------------------
# API request / response
# ---------------------------------------------------------------------------


class SimulateUpgradeRequest(BaseModel):
    target_version: Optional[str] = Field(
        default=None,
        description="Target version to simulate. Defaults to latest_version on the dependency.",
    )
    force_refresh: bool = Field(
        default=False,
        description="Ignore cached completed simulation for the same from→to pair.",
    )


class UpgradeSimulationResponse(IDSchema, TimestampSchema):
    dependency_id: UUID
    repository_id: UUID
    triggered_by_user_id: Optional[UUID] = None
    package_name: str
    from_version: str
    to_version: str
    status: str
    progress_percent: int
    current_stage: Optional[str] = None
    celery_task_id: Optional[str] = None

    summary: Optional[str] = None
    safe_to_upgrade: Optional[bool] = None
    confidence: Optional[float] = None
    readiness_score: Optional[float] = None
    risk_score: Optional[float] = None
    migration_time_hours: Optional[float] = None
    migration_time_label: Optional[str] = None

    breaking_apis: Optional[List[Any]] = None
    deprecated_apis: Optional[List[Any]] = None
    affected_files: Optional[List[Any]] = None
    affected_symbols: Optional[List[Any]] = None
    affected_functions: Optional[List[Any]] = None
    affected_classes: Optional[List[Any]] = None

    security_improvements: Optional[List[Any]] = None
    performance_improvements: Optional[List[Any]] = None
    manual_work_required: Optional[List[Any]] = None
    automatic_fixes_possible: Optional[List[Any]] = None

    migration_plan: Optional[List[Any]] = None
    suggested_changes: Optional[List[Any]] = None
    readiness_factors: Optional[dict] = None

    # Universal Migration Engine enrichments
    migration_rules: Optional[List[Any]] = None
    official_references: Optional[List[str]] = None
    engine_report_id: Optional[str] = None
    collected_sources: Optional[dict] = None
    dynamic_intelligence: Optional[dict] = None
    breaking_classification: Optional[str] = None
    analysis_method: Optional[str] = None
    ai_invoked: Optional[bool] = None
    ai_skipped_reason: Optional[str] = None

    model_used: Optional[str] = None
    error_message: Optional[str] = None
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Worker lifecycle / observability
    last_heartbeat_at: Optional[datetime] = None
    worker_name: Optional[str] = None
    retry_count: int = 0
    cancel_requested: bool = False
    stage_timings: Optional[List[Any]] = None


def enrich_simulation_response(sim: Any) -> "UpgradeSimulationResponse":
    """Attach migration-engine fields from raw/collected payloads."""
    response = UpgradeSimulationResponse.model_validate(sim)
    raw = getattr(sim, "raw_ai_response", None) or {}
    sources = getattr(sim, "collected_sources", None) or {}
    if isinstance(raw, dict):
        # Always surface rules when the engine wrote them (including []).
        if response.migration_rules is None and "rules" in raw:
            response.migration_rules = list(raw.get("rules") or [])
        if response.engine_report_id is None and raw.get("report_id"):
            response.engine_report_id = str(raw.get("report_id"))
        if response.official_references is None and raw.get("official_references") is not None:
            response.official_references = list(raw.get("official_references") or [])
    if isinstance(sources, dict):
        response.collected_sources = sources
        if response.engine_report_id is None and sources.get("migration_engine_report_id"):
            response.engine_report_id = str(sources["migration_engine_report_id"])
        if not response.official_references and sources.get("official_references"):
            response.official_references = list(sources.get("official_references") or [])
        if response.migration_rules is None and sources.get("rules_count") is not None:
            response.migration_rules = []
        intel = sources.get("dynamic_intelligence")
        if isinstance(intel, dict):
            response.dynamic_intelligence = intel
            response.breaking_classification = sources.get("breaking_classification") or intel.get(
                "breaking_classification"
            )
            response.analysis_method = sources.get("analysis_method") or intel.get("analysis_method")
            response.ai_invoked = sources.get("ai_invoked")
            if response.ai_invoked is None:
                response.ai_invoked = intel.get("ai_invoked")
            response.ai_skipped_reason = sources.get("ai_skipped_reason") or intel.get(
                "ai_skipped_reason"
            )
        # Completed runs with zero rules still count as "knowledge finished"
        if isinstance(raw, dict) and not response.dynamic_intelligence and isinstance(
            raw.get("dynamic_intelligence"), dict
        ):
            response.dynamic_intelligence = raw["dynamic_intelligence"]
            response.breaking_classification = response.breaking_classification or raw.get(
                "breaking_classification"
            )
            response.analysis_method = response.analysis_method or raw.get("analysis_source")
    # Terminal simulations without an explicit rules payload → confirmed empty catalog
    status = getattr(sim, "status", None)
    if response.migration_rules is None and status in {"completed", "failed", "cancelled"}:
        response.migration_rules = []
    return response


class UpgradeSimulationListItem(IDSchema, TimestampSchema):
    package_name: str
    from_version: str
    to_version: str
    status: str
    progress_percent: int
    readiness_score: Optional[float] = None
    risk_score: Optional[float] = None
    safe_to_upgrade: Optional[bool] = None
    confidence: Optional[float] = None
    migration_time_label: Optional[str] = None
    completed_at: Optional[datetime] = None
