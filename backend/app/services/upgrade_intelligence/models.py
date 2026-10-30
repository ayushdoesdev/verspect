"""Structured models for Dynamic Upgrade Intelligence."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.services.upgrade_intelligence.categories import CATEGORY_IDS, CATEGORY_TITLES, CategoryId

Completeness = Literal["complete", "partial", "empty"]
AnalysisMethod = Literal["deterministic", "ai", "deterministic+ai"]
ClaimStatus = Literal["verified", "likely", "possible", "unresolved"]
UsageKind = Literal["verified", "probable", "ai_inferred"]
BreakingClassification = Literal[
    "safe",
    "low_risk",
    "potentially_breaking",
    "breaking",
    "unresolved",
]
EvidenceReliability = Literal["high", "medium", "low"]


class EvidenceItem(BaseModel):
    kind: str
    text: str
    source: Optional[str] = None
    reliability: EvidenceReliability = "medium"
    untrusted: bool = True


class AffectedLocation(BaseModel):
    file: str
    line: Optional[int] = None
    column: Optional[int] = None
    api: Optional[str] = None
    reason: str = ""
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    analysis_method: AnalysisMethod = "deterministic"
    usage_kind: UsageKind = "verified"
    snippet: Optional[str] = None


class CategoryFinding(BaseModel):
    category: str
    finding: str
    explanation: str = ""
    affected_files: list[AffectedLocation] = Field(default_factory=list)
    affected_lines: list[int] = Field(default_factory=list)
    required_change: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    source: Optional[str] = None
    analysis_method: AnalysisMethod = "deterministic"
    status: ClaimStatus = "possible"

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


class CategoryResult(BaseModel):
    id: str
    title: str
    deterministic_completeness: Completeness = "empty"
    completeness: Completeness = "empty"
    analysis_method: AnalysisMethod = "deterministic"
    claim_status: ClaimStatus = "unresolved"
    answer: str = ""
    findings: list[CategoryFinding] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    ai_invoked: bool = False
    ai_skipped_reason: Optional[str] = None

    @classmethod
    def blank(cls, category_id: CategoryId) -> "CategoryResult":
        return cls(
            id=category_id,
            title=CATEGORY_TITLES[category_id],
            deterministic_completeness="empty",
            completeness="empty",
            claim_status="unresolved",
        )


class IntelligenceReport(BaseModel):
    package_name: str
    ecosystem: str
    from_version: str
    to_version: str
    breaking_classification: BreakingClassification = "unresolved"
    analysis_method: AnalysisMethod = "deterministic"
    ai_invoked: bool = False
    ai_skipped_reason: Optional[str] = None
    plan_allows_ai: bool = False
    degradation: list[str] = Field(default_factory=list)
    categories: dict[str, CategoryResult] = Field(default_factory=dict)
    affected_files: list[AffectedLocation] = Field(default_factory=list)
    migration_rules: list[dict[str, Any]] = Field(default_factory=list)
    required_changes: list[CategoryFinding] = Field(default_factory=list)
    summary: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sources: list[dict[str, str]] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    catalog_rules_applied: int = 0
    usage_sites: int = 0
    timings: dict[str, Any] = Field(default_factory=dict)

    def category(self, category_id: CategoryId) -> CategoryResult:
        existing = self.categories.get(category_id)
        if existing is not None:
            return existing
        blank = CategoryResult.blank(category_id)
        self.categories[category_id] = blank
        return blank

    def ensure_all_categories(self) -> None:
        for cid in CATEGORY_IDS:
            if cid not in self.categories:
                self.categories[cid] = CategoryResult.blank(cid)

    def to_simulation_overlay(self) -> dict[str, Any]:
        """Fields the simulator UI can merge without replacing stronger evidence."""
        breaking: list[dict[str, Any]] = []
        deprecated: list[dict[str, Any]] = []
        for cid in ("breaking_changes", "removed_apis", "renamed_apis", "changed_signatures"):
            cat = self.categories.get(cid)
            if not cat:
                continue
            for f in cat.findings:
                if f.status == "unresolved":
                    continue
                row = {
                    "api": f.finding,
                    "symbol": f.finding,
                    "fully_qualified_name": f.finding,
                    "change_type": cid,
                    "kind": cid,
                    "description": f.explanation or f.finding,
                    "reason": f.explanation or f.finding,
                    "severity": "high" if f.status == "verified" else "medium",
                    "confidence": f.confidence,
                    "analysis_source": f.analysis_method,
                    "official_reference": f.source,
                    "is_breaking": True,
                    "claim_status": f.status,
                    "affected_files": [loc.file for loc in f.affected_files],
                    "evidence": [
                        {
                            "file_path": loc.file,
                            "line": loc.line,
                            "code_snippet": loc.snippet,
                            "symbol": loc.api,
                        }
                        for loc in f.affected_files
                    ],
                    "required_change": f.required_change,
                }
                breaking.append(row)
        dep_cat = self.categories.get("deprecated_functionality")
        if dep_cat:
            for f in dep_cat.findings:
                deprecated.append(
                    {
                        "symbol": f.finding,
                        "fully_qualified_name": f.finding,
                        "reason": f.explanation or f.finding,
                        "confidence": f.confidence,
                        "analysis_source": f.analysis_method,
                        "official_reference": f.source,
                        "claim_status": f.status,
                        "affected_files": [loc.file for loc in f.affected_files],
                    }
                )
        return {
            "breaking_classification": self.breaking_classification,
            "analysis_method": self.analysis_method,
            "ai_invoked": self.ai_invoked,
            "ai_skipped_reason": self.ai_skipped_reason,
            "degradation": list(self.degradation),
            "breaking_apis": breaking,
            "deprecated_apis": deprecated,
            "affected_files": [loc.model_dump() for loc in self.affected_files],
            "summary": self.summary,
            "confidence": self.confidence,
            "sources": self.sources,
            "migration_rules": self.migration_rules,
            "required_changes": [f.model_dump() for f in self.required_changes],
        }


class EvidenceBundle(BaseModel):
    """Normalized, source-tracked evidence. Never fabricated."""

    package_name: str
    ecosystem: str
    from_version: str
    to_version: str
    registry: dict[str, Any] = Field(default_factory=dict)
    release_notes: list[dict[str, Any]] = Field(default_factory=list)
    github_releases: list[dict[str, Any]] = Field(default_factory=list)
    documentation_urls: list[dict[str, str]] = Field(default_factory=list)
    changelog_excerpts: list[dict[str, Any]] = Field(default_factory=list)
    migration_guide_excerpts: list[dict[str, Any]] = Field(default_factory=list)
    version_history: list[dict[str, Any]] = Field(default_factory=list)
    breaking_change_hints: list[str] = Field(default_factory=list)
    deprecated_hints: list[str] = Field(default_factory=list)
    security_hints: list[str] = Field(default_factory=list)
    extracted_changes: list[dict[str, Any]] = Field(default_factory=list)
    items: list[EvidenceItem] = Field(default_factory=list)
    degradation: list[str] = Field(default_factory=list)
    github_repo_url: Optional[str] = None
    latest_version: Optional[str] = None
    raw_sources: dict[str, Any] = Field(default_factory=dict)
