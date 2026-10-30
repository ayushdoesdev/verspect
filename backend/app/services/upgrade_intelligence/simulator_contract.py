"""Upgrade Simulator persistence contract.

The migration engine may still emit catalog-missing ``unknown`` findings for
patch generation. The Upgrade Simulator must not present those as the impact
verdict once Dynamic Upgrade Intelligence has run.
"""

from __future__ import annotations

from typing import Any, Optional

from app.services.upgrade_helpers import (
    MIGRATION_STATUS_MANUAL,
    MIGRATION_STATUS_NO_CHANGE,
    MIGRATION_STATUS_UNKNOWN,
    MIGRATION_STATUS_UNRESOLVED,
    STATUS_TITLE,
    build_migration_finding,
)
from app.services.upgrade_intelligence.models import IntelligenceReport

INTELLIGENCE_SCHEMA_VERSION = 2

INCOMPLETE_AI_FLAGS = (
    "ai_timeout",
    "ai_unavailable",
    "ai_rate_limited",
    "malformed_ai_response",
    "ai_completion_failed",
)

LEGACY_UNKNOWN_MARKERS = (
    "insufficient deterministic knowledge",
    "insufficient deterministic migration knowledge",
    "no structured migration rules",
    "do not treat as a clean upgrade",
    "do not treat this as a clean upgrade",
)


def is_legacy_catalog_unknown(row: dict[str, Any]) -> bool:
    """True for the pre-intelligence 'Unknown — no catalog' placeholder."""
    if row.get("analysis_source"):
        return False
    if row.get("unknown") is True:
        return True
    blob = " ".join(
        str(row.get(k) or "")
        for k in ("explanation", "status_detail", "status_title", "reason")
    ).lower()
    if not blob:
        return row.get("migration_status") == MIGRATION_STATUS_UNKNOWN
    return any(marker in blob for marker in LEGACY_UNKNOWN_MARKERS)


def cached_simulation_is_current(sim: Any) -> bool:
    """Reuse completed cache only for current, successful-enough intelligence.

    Timed-out / unavailable / malformed AI runs stay in history but are not
    treated as a finished result for automatic reuse.
    """
    sources = getattr(sim, "collected_sources", None) or {}
    if not isinstance(sources, dict):
        return False
    if sources.get("intelligence_schema_version") != INTELLIGENCE_SCHEMA_VERSION:
        return False
    intel = sources.get("dynamic_intelligence")
    if not isinstance(intel, dict) or not intel.get("categories"):
        return False
    deg = set(intel.get("degradation") or [])
    if deg.intersection(INCOMPLETE_AI_FLAGS):
        return False
    skipped = intel.get("ai_skipped_reason") or sources.get("ai_skipped_reason")
    if skipped in INCOMPLETE_AI_FLAGS:
        return False
    return True


def apply_intelligence_to_simulator_findings(
    suggested: list[dict[str, Any]],
    intelligence: IntelligenceReport,
    *,
    package_name: str,
) -> list[dict[str, Any]]:
    """Replace catalog-missing Unknown rows with intelligence-backed findings.

    Automatic patches from a real catalog are kept. AI never overwrites those.
    """
    kept: list[dict[str, Any]] = []
    stripped_unknown = False
    for row in suggested:
        if is_legacy_catalog_unknown(row):
            stripped_unknown = True
            continue
        kept.append(row)

    existing = {
        (
            str(s.get("file_path") or ""),
            s.get("line"),
            str(s.get("symbol") or ""),
        )
        for s in kept
    }

    for finding in intelligence.required_changes:
        loc = finding.affected_files[0] if finding.affected_files else None
        path = loc.file if loc else "(repository)"
        line = loc.line if loc else None
        key = (path, line, finding.finding)
        if key in existing:
            continue
        existing.add(key)
        rec = build_migration_finding(
            file_path=path,
            line=line,
            symbol=finding.finding,
            current_code=(loc.snippet if loc else "") or "",
            suggested_code=None,
            explanation=finding.required_change or finding.explanation,
            confidence=finding.confidence,
            automatic=False,
            official_reference=finding.source,
            risk_flagged=True,
        )
        rec["analysis_source"] = finding.analysis_method
        rec["claim_status"] = finding.status
        kept.append(rec)

    if stripped_unknown or not kept:
        kept.extend(
            _intelligence_usage_findings(intelligence, package_name, existing)
        )

    if not kept:
        kept.append(_repository_verdict_finding(intelligence, package_name))

    _reclassify_unmatched_no_change_rows(kept, intelligence)
    return kept


def simulator_summary(
    intelligence: IntelligenceReport,
    *,
    engine_summary: Optional[str] = None,
    catalog_matched: bool = False,
) -> str:
    """Prefer evidence-backed intelligence. Never keep catalog-Unknown as the headline."""
    intel = (intelligence.summary or "").strip()
    engine = (engine_summary or "").strip()
    if intel:
        if catalog_matched and engine and intel not in engine:
            return f"{engine} {intel}"
        return intel
    if engine and not any(m in engine.lower() for m in LEGACY_UNKNOWN_MARKERS):
        return engine
    return intel or engine or "Upgrade analysis completed."


def simulator_confidence(
    intelligence: IntelligenceReport,
    *,
    engine_confidence: float,
    catalog_matched: bool,
) -> float:
    """Engine 0.3 Unknown scoring must not win once intelligence has run."""
    intel = float(intelligence.confidence or 0.0)
    if catalog_matched:
        return max(float(engine_confidence or 0.0), intel)
    return intel if intel else float(engine_confidence or 0.0)


def _required_change_categories_incomplete(intelligence: IntelligenceReport) -> bool:
    """True when required edits or migration steps were not fully established."""
    for cid in ("required_code_changes", "migration_steps"):
        cat = intelligence.categories.get(cid)
        if cat is None:
            continue
        if cat.completeness in {"empty", "partial"} or cat.claim_status == "unresolved":
            return True
    return False


def _reclassify_unmatched_no_change_rows(
    rows: list[dict[str, Any]],
    intelligence: IntelligenceReport,
) -> None:
    """Do not present unmatched usage as a clean upgrade when Analysis is unresolved.

    The migration engine emits ``no_migration_required`` when rules exist but none
    match a usage site. That is not the same as proving the upgrade needs no edits.
    """
    if not _required_change_categories_incomplete(intelligence):
        return
    detail = (
        "No per-file patch was generated for this usage. "
        "Required-change or migration-step analysis is still unresolved. "
        "This is not a verified clean upgrade — see the Analysis tab."
    )
    for row in rows:
        blob = f"{row.get('explanation') or ''} {row.get('status_detail') or ''}".lower()
        if "none match this usage" not in blob:
            continue
        if row.get("migration_status") not in {MIGRATION_STATUS_NO_CHANGE, None, ""}:
            continue
        if (row.get("suggested_code") or "").strip():
            continue
        row["migration_status"] = MIGRATION_STATUS_UNRESOLVED
        row["status_title"] = STATUS_TITLE[MIGRATION_STATUS_UNRESOLVED]
        row["status_detail"] = detail
        row["explanation"] = detail
        row["unknown"] = False
        row["automatic"] = False
        row["analysis_source"] = row.get("analysis_source") or intelligence.analysis_method


def _intelligence_usage_findings(
    intelligence: IntelligenceReport,
    package_name: str,
    existing: set[tuple],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    why = intelligence.categories.get("why_file_affected")
    locations = list(intelligence.affected_files)
    if why and why.findings:
        for f in why.findings:
            locations.extend(f.affected_files)
    seen: set[tuple] = set(existing)
    for loc in locations:
        path = loc.file or ""
        if not path:
            continue
        key = (path, loc.line, loc.api or package_name)
        if key in seen:
            continue
        seen.add(key)
        rec = _usage_verdict_finding(intelligence, package_name, loc.file, loc.line, loc.api, loc.snippet, loc.reason)
        out.append(rec)
    return out


def _usage_verdict_finding(
    intelligence: IntelligenceReport,
    package_name: str,
    file_path: str,
    line: Optional[int],
    api: Optional[str],
    snippet: Optional[str],
    reason: Optional[str],
) -> dict[str, Any]:
    title, detail, status = _verdict_copy(intelligence)
    rec = build_migration_finding(
        file_path=file_path,
        line=line,
        symbol=api or package_name,
        current_code=snippet or "",
        suggested_code=None,
        explanation=detail,
        confidence=max(float(intelligence.confidence or 0.4), 0.35),
        automatic=False,
        risk_flagged=status != MIGRATION_STATUS_NO_CHANGE,
    )
    rec["migration_status"] = status
    rec["status_title"] = title
    rec["status_detail"] = (reason + " " + detail).strip() if reason else detail
    rec["explanation"] = rec["status_detail"]
    rec["analysis_source"] = intelligence.analysis_method
    rec["claim_status"] = intelligence.categories.get("upgrade_risk").claim_status if intelligence.categories.get("upgrade_risk") else "possible"
    rec["unknown"] = False
    if status == MIGRATION_STATUS_UNRESOLVED:
        rec["confidence"] = min(float(rec.get("confidence") or 0.4), 0.5)
    return rec


def _repository_verdict_finding(
    intelligence: IntelligenceReport,
    package_name: str,
) -> dict[str, Any]:
    title, detail, status = _verdict_copy(intelligence)
    rec = build_migration_finding(
        file_path="(repository)",
        line=None,
        symbol=package_name,
        current_code="",
        suggested_code=None,
        explanation=detail,
        confidence=max(float(intelligence.confidence or 0.4), 0.35),
        automatic=False,
        risk_flagged=status != MIGRATION_STATUS_NO_CHANGE,
    )
    rec["migration_status"] = status
    rec["status_title"] = title
    rec["status_detail"] = detail
    rec["explanation"] = detail
    rec["analysis_source"] = intelligence.analysis_method
    rec["unknown"] = False
    if status == MIGRATION_STATUS_UNRESOLVED:
        rec["confidence"] = min(float(rec.get("confidence") or 0.4), 0.5)
    return rec


def _verdict_copy(intelligence: IntelligenceReport) -> tuple[str, str, str]:
    cls = intelligence.breaking_classification
    skipped = intelligence.ai_skipped_reason
    degradation = set(intelligence.degradation or [])
    method = intelligence.analysis_method

    if skipped == "plan_does_not_include_ai":
        return (
            "Deterministic analysis",
            "Additional AI analysis requires a plan that includes AI (Pro, Team, or Enterprise). "
            "Deterministic usage and documentation findings are shown.",
            MIGRATION_STATUS_MANUAL,
        )
    if "ai_timeout" in degradation or skipped == "ai_timeout":
        return (
            "AI-assisted analysis timed out",
            "AI-assisted analysis timed out before a structured result was ready. "
            "Deterministic evidence is preserved. This is not a complete result.",
            MIGRATION_STATUS_UNRESOLVED,
        )
    if "ai_rate_limited" in degradation or skipped == "ai_rate_limited":
        return (
            "AI-assisted analysis rate-limited",
            "The AI provider rate-limited or quota-limited this request. "
            "Deterministic evidence is preserved.",
            MIGRATION_STATUS_UNRESOLVED,
        )
    if "ai_unavailable" in degradation or skipped == "ai_unavailable":
        return (
            "AI-assisted analysis unavailable",
            "AI-assisted analysis is currently unavailable. Deterministic evidence is preserved. "
            "This is not a complete result.",
            MIGRATION_STATUS_UNRESOLVED,
        )
    if "malformed_ai_response" in degradation:
        return (
            "AI returned a malformed response",
            "AI output could not be validated. Deterministic evidence is preserved.",
            MIGRATION_STATUS_UNRESOLVED,
        )
    if "ai_completion_failed" in degradation:
        return (
            "AI-assisted analysis unavailable",
            "AI-assisted analysis is currently unavailable. Deterministic evidence is preserved. "
            "This is not a complete result.",
            MIGRATION_STATUS_UNRESOLVED,
        )
    if cls == "breaking":
        return (
            "AI-assisted analysis — breaking" if method != "deterministic" else "Verified breaking changes",
            intelligence.summary
            or "Verified breaking changes affect this repository. Review required code changes.",
            MIGRATION_STATUS_MANUAL,
        )
    if cls == "potentially_breaking":
        return (
            "AI-assisted analysis — potentially breaking" if "ai" in method else "Potentially breaking",
            intelligence.summary
            or "Documented changes overlap indexed usage. Manual review is required.",
            MIGRATION_STATUS_MANUAL,
        )
    if cls in {"safe", "low_risk"}:
        title = (
            "AI-assisted analysis — low risk"
            if "ai" in method
            else "Low risk for indexed usage"
        )
        return (
            title,
            intelligence.summary
            or "No verified breaking impact on indexed usage. A missing catalog is not a clean-upgrade claim.",
            MIGRATION_STATUS_MANUAL,
        )
    return (
        "Unresolved",
        intelligence.summary
        or "Unresolved — insufficient evidence after deterministic and AI analysis.",
        MIGRATION_STATUS_UNRESOLVED,
    )
