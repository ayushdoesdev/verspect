"""Dynamic Upgrade Intelligence orchestrator.

Deterministic analysis first. Per-category AI fallback only when allowed and needed.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from app.core.logging import get_logger
from app.services.upgrade_impact import UpgradeImpactAnalyzer, UpgradeImpactReport
from app.services.upgrade_intelligence.ai_fill import CategoryAIFiller
from app.services.upgrade_intelligence.categories import CATEGORY_IDS
from app.services.upgrade_intelligence.deterministic import DeterministicCategoryAnalyzer
from app.services.upgrade_intelligence.evidence import (
    GeneralizedEvidenceCollector,
    normalize_ecosystem,
)
from app.services.upgrade_intelligence.merge import (
    classify_breaking,
    combine_method,
    incomplete_category_ids,
    overall_confidence,
)
from app.services.upgrade_intelligence.models import EvidenceBundle, IntelligenceReport

logger = get_logger(__name__)

_PAID_PLAN_MESSAGE = (
    "Additional AI analysis requires a plan that includes AI (Pro, Team, or Enterprise). "
    "Deterministic findings are shown below."
)


class DynamicUpgradeIntelligence:
    def __init__(
        self,
        *,
        collector: Optional[GeneralizedEvidenceCollector] = None,
        deterministic: Optional[DeterministicCategoryAnalyzer] = None,
        impact_analyzer: Optional[UpgradeImpactAnalyzer] = None,
    ) -> None:
        self.collector = collector or GeneralizedEvidenceCollector()
        self.deterministic = deterministic or DeterministicCategoryAnalyzer()
        self.impact_analyzer = impact_analyzer or UpgradeImpactAnalyzer()

    def analyze(
        self,
        *,
        package_name: str,
        current_version: str,
        target_version: str,
        usages: list[dict[str, Any]],
        ecosystem: str = "PyPI",
        allow_ai: bool = False,
        ai: Any = None,
        github_url: Optional[str] = None,
        existing_releases: Optional[list[dict[str, Any]]] = None,
        cve_hints: Optional[list[str]] = None,
        latest_version: Optional[str] = None,
        graph_neighbors: Optional[list[str]] = None,
        lockfile_note: Optional[str] = None,
        evidence: Optional[EvidenceBundle] = None,
        impact: Optional[UpgradeImpactReport] = None,
        skip_network: bool = False,
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
    ) -> IntelligenceReport:
        eco = normalize_ecosystem(ecosystem)
        started = time.perf_counter()
        evidence_seconds = 0.0
        deterministic_seconds = 0.0
        ai_seconds = 0.0
        ai_calls = 0
        if not target_version:
            empty = EvidenceBundle(
                package_name=package_name,
                ecosystem=eco,
                from_version=current_version or "",
                to_version="",
                degradation=["invalid_target_version"],
            )
            evidence = evidence or empty

        if evidence is None:
            t0 = time.perf_counter()
            evidence = self.collector.collect(
                package_name=package_name,
                from_version=current_version,
                to_version=target_version,
                ecosystem=eco,
                github_repo_url=github_url,
                existing_releases=existing_releases,
                cve_summaries=cve_hints,
                skip_network=skip_network,
            )
            evidence_seconds = time.perf_counter() - t0

        if impact is None:
            impact = self.impact_analyzer.analyze(
                package_name=package_name,
                current_version=current_version,
                target_version=target_version,
                usages=usages,
            )

        t_det = time.perf_counter()
        report = self.deterministic.analyze(
            package_name=package_name,
            ecosystem=eco,
            current_version=current_version,
            target_version=target_version,
            usages=usages,
            impact=impact,
            evidence=evidence,
            latest_version=latest_version,
            graph_neighbors=graph_neighbors,
            lockfile_note=lockfile_note,
        )
        deterministic_seconds = time.perf_counter() - t_det
        report.plan_allows_ai = bool(allow_ai)
        report.ensure_all_categories()

        incomplete = incomplete_category_ids(report)
        if not incomplete:
            report.ai_skipped_reason = "all_categories_complete"
        elif not allow_ai:
            report.ai_skipped_reason = "plan_does_not_include_ai"
            report.degradation.append("ai_disabled_by_plan")
            for cid in incomplete:
                cat = report.category(cid)
                cat.ai_skipped_reason = "plan_does_not_include_ai"
                if cat.completeness != "complete":
                    extra = _PAID_PLAN_MESSAGE
                    if extra not in (cat.answer or ""):
                        cat.answer = ((cat.answer or "").strip() + " " + extra).strip()
        else:
            filler = CategoryAIFiller(ai)
            t_ai = time.perf_counter()
            report, err = filler.fill(
                report,
                incomplete=incomplete,
                evidence=evidence,
                usages=usages,
                repository_id=repository_id,
                dependency_id=dependency_id,
            )
            ai_seconds = time.perf_counter() - t_ai
            ai_calls = 1 if filler.available else 0
            if err:
                specific = {
                    "ai_timeout",
                    "ai_unavailable",
                    "ai_rate_limited",
                    "malformed_ai_response",
                }
                if not (specific & set(report.degradation or [])):
                    report.degradation.append("ai_completion_failed")
                if err not in report.summary:
                    report.summary = (
                        (report.summary or "Partial analysis available.")
                        + " "
                        + err
                    ).strip()

        report.ensure_all_categories()
        report.breaking_classification = classify_breaking(report)  # type: ignore[assignment]
        report.analysis_method = combine_method(report)
        report.confidence = overall_confidence(report)
        report.summary = self._compose_summary(report)
        prior = dict(report.timings or {})
        report.timings = {
            "evidence_seconds": round(evidence_seconds, 3),
            "deterministic_seconds": round(deterministic_seconds, 3),
            "ai_seconds": round(ai_seconds, 3),
            "total_seconds": round(time.perf_counter() - started, 3),
            "incomplete_categories": len(incomplete),
            "ai_calls": ai_calls,
            **prior,
        }
        logger.info(
            "upgrade_intelligence_timings",
            package=package_name,
            evidence_seconds=report.timings["evidence_seconds"],
            deterministic_seconds=report.timings["deterministic_seconds"],
            ai_seconds=report.timings["ai_seconds"],
            total_seconds=report.timings["total_seconds"],
            incomplete_categories=report.timings["incomplete_categories"],
            ai_calls=report.timings["ai_calls"],
            prompt_chars=report.timings.get("prompt_chars"),
            ai_response_chars=report.timings.get("ai_response_chars"),
        )

        # Keep required_changes in sync after AI fill.
        code_cat = report.categories.get("required_code_changes")
        if code_cat:
            report.required_changes = list(code_cat.findings)
        rules_cat = report.categories.get("migration_rules")
        if rules_cat and rules_cat.findings:
            existing_syms = {r.get("symbol") for r in report.migration_rules}
            for f in rules_cat.findings:
                if f.finding in existing_syms:
                    continue
                report.migration_rules.append(
                    {
                        "symbol": f.finding,
                        "kind": f.category,
                        "description": f.explanation,
                        "reason": f.explanation,
                        "severity": "medium",
                        "confidence": f.confidence,
                        "auto_fixable": False,
                        "official_reference": f.source,
                        "analysis_source": f.analysis_method,
                        "required_change": f.required_change,
                    }
                )
        return report

    def _compose_summary(self, report: IntelligenceReport) -> str:
        cls_label = {
            "breaking": "Verified breaking changes affect this repository.",
            "potentially_breaking": "The upgrade is potentially breaking for this repository.",
            "low_risk": "No verified breaking impact on indexed usage.",
            "safe": "No impact detected in this repository.",
            "unresolved": "Impact is not fully resolved from available evidence.",
        }.get(report.breaking_classification, "Upgrade analysis completed.")
        method = {
            "deterministic": "Deterministic analysis.",
            "ai": "AI analysis (no complete deterministic coverage).",
            "deterministic+ai": "Deterministic analysis with AI fill for incomplete categories.",
        }.get(report.analysis_method, "")
        bits = [cls_label, method]
        if "ai_disabled_by_plan" in report.degradation:
            bits.append(_PAID_PLAN_MESSAGE)
        elif "ai_timeout" in report.degradation:
            bits.append("Partial analysis available. AI-assisted analysis timed out.")
        elif "ai_rate_limited" in report.degradation:
            bits.append("Partial analysis available. AI provider rate-limited the request.")
        elif "ai_unavailable" in report.degradation or "ai_completion_failed" in report.degradation:
            bits.append("Partial analysis available. AI completion is currently unavailable.")
        elif "malformed_ai_response" in report.degradation:
            bits.append("Partial analysis available. AI output could not be validated.")
        if "package_registry_unavailable" in report.degradation:
            bits.append("Package registry was unavailable.")
        filled = sum(1 for c in report.categories.values() if c.completeness != "empty")
        bits.append(f"{filled}/{len(CATEGORY_IDS)} categories have an evidence-backed answer.")
        return " ".join(b for b in bits if b)
