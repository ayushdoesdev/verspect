"""Merge deterministic category results with structured AI fills.

AI never overwrites stronger deterministic evidence.
"""

from __future__ import annotations

from typing import Optional

from app.services.upgrade_intelligence.categories import CATEGORY_IDS, CategoryId
from app.services.upgrade_intelligence.models import (
    AffectedLocation,
    AnalysisMethod,
    CategoryFinding,
    CategoryResult,
    ClaimStatus,
    IntelligenceReport,
)

_STATUS_RANK: dict[ClaimStatus, int] = {
    "unresolved": 0,
    "possible": 1,
    "likely": 2,
    "verified": 3,
}

_METHOD_RANK: dict[AnalysisMethod, int] = {
    "ai": 0,
    "deterministic": 1,
    "deterministic+ai": 2,
}


def _finding_key(finding: CategoryFinding) -> tuple[str, str, str]:
    files = ",".join(sorted({loc.file for loc in finding.affected_files}))
    return (finding.category, (finding.finding or "").lower(), files)


def merge_findings(
    deterministic: list[CategoryFinding],
    ai: list[CategoryFinding],
) -> list[CategoryFinding]:
    by_key: dict[tuple[str, str, str], CategoryFinding] = {}
    for finding in deterministic:
        by_key[_finding_key(finding)] = finding
    for finding in ai:
        key = _finding_key(finding)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = finding
            continue
        # Never let AI overwrite stronger deterministic evidence.
        if _STATUS_RANK.get(existing.status, 0) >= _STATUS_RANK.get(finding.status, 0):
            if existing.analysis_method == "deterministic" and finding.analysis_method == "ai":
                existing.analysis_method = "deterministic+ai"
                if finding.explanation and finding.explanation not in (existing.explanation or ""):
                    existing.explanation = (existing.explanation + " " + finding.explanation).strip()
                if finding.required_change and not existing.required_change:
                    existing.required_change = finding.required_change
            continue
        if existing.analysis_method == "deterministic":
            finding.analysis_method = "deterministic+ai"
            finding.evidence = list(existing.evidence) + list(finding.evidence)
            finding.affected_files = _merge_locations(existing.affected_files, finding.affected_files)
        by_key[key] = finding
    return list(by_key.values())


def _merge_locations(
    left: list[AffectedLocation],
    right: list[AffectedLocation],
) -> list[AffectedLocation]:
    seen: set[tuple[str, Optional[int], str]] = set()
    out: list[AffectedLocation] = []
    for loc in list(left) + list(right):
        key = (loc.file, loc.line, loc.api or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(loc)
    return out


def apply_ai_category(
    result: CategoryResult,
    ai_findings: list[CategoryFinding],
    ai_answer: str,
    *,
    claim_status: ClaimStatus = "possible",
) -> CategoryResult:
    if result.deterministic_completeness == "complete" and result.findings:
        # Keep deterministic; optionally annotate method if AI added nothing new.
        return result
    merged = merge_findings(result.findings, ai_findings)
    method: AnalysisMethod
    if result.deterministic_completeness == "empty":
        method = "ai"
        completeness = "complete" if merged else "empty"
    else:
        method = "deterministic+ai"
        completeness = "complete" if merged else result.completeness
    answer = result.answer
    if ai_answer:
        if result.deterministic_completeness == "empty":
            answer = ai_answer
        elif ai_answer not in answer:
            answer = (answer + " " + ai_answer).strip()
    status = result.claim_status
    if _STATUS_RANK.get(claim_status, 0) > _STATUS_RANK.get(status, 0):
        # AI may raise unresolved → possible/likely, never invent verified without det. evidence.
        if claim_status == "verified" and result.deterministic_completeness == "empty":
            status = "likely"
        else:
            status = claim_status if claim_status != "verified" else (
                "verified" if result.deterministic_completeness != "empty" else "likely"
            )
    result.findings = merged
    result.answer = answer
    result.completeness = completeness  # type: ignore[assignment]
    result.analysis_method = method
    result.claim_status = status
    result.ai_invoked = True
    return result


def classify_breaking(report: IntelligenceReport) -> str:
    """Recompute breaking classification. Major version is never sufficient alone."""
    breaking = report.categories.get("breaking_changes")
    verified = report.categories.get("upgrade_verified_breaking")
    findings = list(breaking.findings) if breaking else []
    has_verified = any(
        f.status == "verified" and f.affected_files for f in findings
    ) or (verified and verified.answer.lower().startswith("yes") and verified.claim_status == "verified")
    has_usage_overlap = any(
        f.status in {"likely", "possible"} and f.affected_files for f in findings
    )
    if has_verified:
        return "breaking"
    if has_usage_overlap:
        return "potentially_breaking"
    if report.usage_sites == 0:
        return "safe"
    if breaking and breaking.completeness in {"complete", "partial"}:
        # Package-level notes with no overlap on indexed usage are not repo-breaking.
        return "low_risk"
    return "unresolved"


def combine_method(report: IntelligenceReport) -> AnalysisMethod:
    methods = {c.analysis_method for c in report.categories.values()}
    if "deterministic+ai" in methods or ("deterministic" in methods and "ai" in methods):
        return "deterministic+ai"
    if "ai" in methods and "deterministic" not in methods:
        return "ai"
    return "deterministic"


def overall_confidence(report: IntelligenceReport) -> float:
    scores = [c.findings[0].confidence for c in report.categories.values() if c.findings]
    if not scores:
        return report.confidence
    return max(0.0, min(1.0, sum(scores) / len(scores) * 0.35 + max(scores) * 0.65))


def incomplete_category_ids(report: IntelligenceReport) -> list[CategoryId]:
    out: list[CategoryId] = []
    for cid in CATEGORY_IDS:
        cat = report.categories.get(cid)
        if cat is None or cat.deterministic_completeness in {"partial", "empty"}:
            out.append(cid)
    return out
