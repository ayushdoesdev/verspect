"""Celery task — AI Upgrade Impact Simulator pipeline."""

from __future__ import annotations

import time
import traceback
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update

from app.ai.upgrade_simulator import build_cache_key, usage_fingerprint
from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.database import SyncSessionLocal
from app.core.enums import SimulationStatus
from app.core.logging import get_logger
from app.services.job_health import close_stage_timings, record_stage_timing
from app.models.cve import CVE
from app.models.dependency import Dependency
from app.models.library_usage import LibraryUsage
from app.models.release import Release
from app.models.upgrade_simulation import UpgradeSimulation
from app.services.upgrade_sources import UpgradeSourceCollector

logger = get_logger(__name__)
_settings = get_settings()

TERMINAL_SIMULATION_STATUSES = frozenset(
    {
        SimulationStatus.COMPLETED.value,
        SimulationStatus.FAILED.value,
        SimulationStatus.CANCELLED.value,
    }
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _simulation_is_terminal(sim: UpgradeSimulation) -> bool:
    return (sim.status or "") in TERMINAL_SIMULATION_STATUSES


def _try_claim_simulation(
    session,
    sim: UpgradeSimulation,
    *,
    owner_task_id: str,
    worker_name: str | None,
    retry_count: int | None = None,
) -> bool:
    """Atomically claim a simulation. Concurrent cancel always wins."""
    now = _utcnow()
    values: dict[str, Any] = {
        "status": SimulationStatus.COLLECTING_SOURCES.value,
        "progress_percent": 8,
        "current_stage": "preparing",
        "celery_task_id": owner_task_id,
        "started_at": now,
        "worker_name": worker_name,
        "last_heartbeat_at": now,
        "stage_timings": record_stage_timing(sim.stage_timings, "preparing", now=now),
    }
    if retry_count is not None:
        values["retry_count"] = int(retry_count)

    result = session.execute(
        update(UpgradeSimulation)
        .where(
            UpgradeSimulation.id == sim.id,
            UpgradeSimulation.cancel_requested.is_(False),
            UpgradeSimulation.status.notin_(tuple(TERMINAL_SIMULATION_STATUSES)),
        )
        .values(**values)
    )
    session.commit()
    session.refresh(sim)
    return int(result.rowcount or 0) == 1


def _set_progress(session, sim: UpgradeSimulation, status: str, percent: int, stage: str) -> None:
    """Persist simulation progress plus a worker heartbeat and stage timing."""
    now = _utcnow()
    sim.status = status
    sim.progress_percent = percent
    sim.current_stage = stage
    sim.stage_timings = record_stage_timing(sim.stage_timings, stage, now=now)
    sim.last_heartbeat_at = now
    session.commit()


def _is_simulation_cancelled(session, simulation_id: str) -> bool:
    """Cooperative cancellation checkpoint for the simulation pipeline.

    Refresh ONLY the simulation row. Never expire the whole session — that
    discards unflushed ORM mutations (same class of bug as scans).
    """
    sim = session.get(UpgradeSimulation, UUID(simulation_id))
    if sim is None:
        return True
    session.refresh(sim)
    if sim.cancel_requested and sim.status != SimulationStatus.CANCELLED.value:
        now = _utcnow()
        sim.status = SimulationStatus.CANCELLED.value
        sim.current_stage = "cancelled"
        sim.completed_at = now
        sim.stage_timings = close_stage_timings(sim.stage_timings, now=now)
        session.commit()
        logger.info("simulation_cancelled_midflight", simulation_id=simulation_id)
        return True
    return sim.status == SimulationStatus.CANCELLED.value


@celery_app.task(
    bind=True,
    name="app.services.tasks.upgrade_simulation_tasks.run_upgrade_simulation",
    max_retries=_settings.job_max_auto_retries,
    soft_time_limit=_settings.simulation_soft_time_limit_seconds,
    time_limit=_settings.simulation_hard_time_limit_seconds,
)
def run_upgrade_simulation(self, simulation_id: str) -> dict[str, Any]:
    session = SyncSessionLocal()
    worker_name = getattr(self.request, "hostname", None)
    try:
        sim = session.get(UpgradeSimulation, UUID(simulation_id))
        if sim is None:
            logger.error("upgrade_simulation_not_found", simulation_id=simulation_id)
            return {"error": "not_found"}

        if _simulation_is_terminal(sim):
            logger.info(
                "simulation_skipped_terminal",
                simulation_id=simulation_id,
                status=sim.status,
            )
            return {
                "simulation_id": simulation_id,
                "status": sim.status,
                "skipped": "terminal",
            }

        if sim.cancel_requested:
            logger.info("simulation_skipped_cancelled", simulation_id=simulation_id)
            return {"simulation_id": simulation_id, "status": "cancelled"}

        claimed = _try_claim_simulation(
            session,
            sim,
            owner_task_id=self.request.id,
            worker_name=worker_name,
            retry_count=int(self.request.retries) if self.request.retries else None,
        )
        if not claimed:
            logger.info(
                "simulation_claim_lost",
                simulation_id=simulation_id,
                status=sim.status,
                cancel_requested=sim.cancel_requested,
            )
            if sim.cancel_requested or sim.status == SimulationStatus.CANCELLED.value:
                return {"simulation_id": simulation_id, "status": "cancelled"}
            if _simulation_is_terminal(sim):
                return {
                    "simulation_id": simulation_id,
                    "status": sim.status,
                    "skipped": "terminal",
                }
            return {"simulation_id": simulation_id, "status": "claim_failed"}

        logger.info(
            "simulation_picked_up",
            simulation_id=simulation_id,
            worker=worker_name,
            retries=self.request.retries,
        )

        dep = session.get(Dependency, sim.dependency_id)
        if dep is None:
            sim.status = SimulationStatus.FAILED.value
            sim.error_message = "Dependency not found"
            sim.completed_at = _utcnow()
            session.commit()
            return {"error": "dependency_not_found"}

        # STEP 2 — Load API usages from AST index
        usages_orm = (
            session.execute(
                select(LibraryUsage).where(LibraryUsage.dependency_id == dep.id)
            )
            .scalars()
            .all()
        )
        usages = [
            {
                "package_name": u.package_name,
                "module_path": u.module_path,
                "symbol": u.symbol,
                "fully_qualified_name": u.fully_qualified_name,
                "usage_kind": u.usage_kind,
                "file_path": u.file_path,
                "line": u.line,
                "column": u.column,
                "enclosing_function": u.enclosing_function,
                "enclosing_class": u.enclosing_class,
                "code_snippet": u.code_snippet,
                "extra_metadata": u.extra_metadata or {},
                "keyword_args": (u.extra_metadata or {}).get("keyword_args") or [],
            }
            for u in usages_orm
        ]
        sim.usage_snapshot = usages
        session.commit()
        _set_progress(
            session,
            sim,
            SimulationStatus.COLLECTING_SOURCES.value,
            18,
            "detecting_api",
        )

        # Existing release analyses + CVEs for context
        releases = (
            session.execute(select(Release).where(Release.dependency_id == dep.id))
            .scalars()
            .all()
        )
        existing_releases = [
            {
                "version": r.version,
                "ai_summary": r.ai_summary,
                "breaking_changes": r.breaking_changes,
                "deprecated_apis": r.deprecated_apis,
                "has_breaking_changes": r.has_breaking_changes,
                "risk_score": r.risk_score,
            }
            for r in releases
        ]
        cves = (
            session.execute(select(CVE).where(CVE.dependency_id == dep.id))
            .scalars()
            .all()
        )
        cve_hints = []
        for c in cves:
            if c.fixed_version:
                cve_hints.append(
                    f"{c.osv_id}: fixed in {c.fixed_version} — {c.summary[:200]}"
                )
            else:
                cve_hints.append(f"{c.osv_id}: {c.summary[:200]}")

        # STEP 3 — Collect generalized evidence (registry + releases + changelog)
        from app.services.upgrade_intelligence.evidence import GeneralizedEvidenceCollector
        from app.services.upgrade_intelligence.models import EvidenceBundle

        evidence_bundle: EvidenceBundle
        evidence_started = time.perf_counter()
        try:
            evidence_bundle = GeneralizedEvidenceCollector().collect(
                package_name=dep.package_name,
                from_version=sim.from_version,
                to_version=sim.to_version,
                ecosystem=dep.ecosystem or "PyPI",
                github_repo_url=dep.github_repo_url,
                existing_releases=existing_releases,
                cve_summaries=cve_hints,
            )
            sources = dict(evidence_bundle.raw_sources or {})
        except Exception as ev_exc:  # noqa: BLE001
            logger.warning(
                "upgrade_evidence_collect_failed",
                simulation_id=simulation_id,
                error=str(ev_exc)[:400],
            )
            collector = UpgradeSourceCollector()
            sources = collector.collect(
                package_name=dep.package_name,
                from_version=sim.from_version,
                to_version=sim.to_version,
                github_repo_url=dep.github_repo_url,
                existing_releases=existing_releases,
                cve_summaries=cve_hints,
                ecosystem=dep.ecosystem or "PyPI",
            )
            evidence_bundle = EvidenceBundle(
                package_name=dep.package_name,
                ecosystem=dep.ecosystem or "PyPI",
                from_version=sim.from_version,
                to_version=sim.to_version,
                raw_sources=sources,
                github_repo_url=dep.github_repo_url,
                degradation=["package_registry_unavailable"],
            )
        evidence_seconds = round(time.perf_counter() - evidence_started, 3)
        sources.setdefault("degradation", list(evidence_bundle.degradation))
        sources["extracted_changes"] = evidence_bundle.extracted_changes[:80]
        sim.collected_sources = sources
        _set_progress(
            session,
            sim,
            SimulationStatus.ANALYZING_IMPACT.value,
            32,
            "matching_rules",
        )

        from app.ai.upgrade_simulator import UpgradeImpactAnalyzer
        from app.migration_engine.migration_service import MigrationService
        from app.services.upgrade_helpers import (
            build_ast_affected_files,
            build_migration_finding,
            code_differs,
            collect_official_references,
            confidence_label,
            findings_to_suggested_changes,
            rule_annotations_by_file,
            sanitize_engine_error,
        )

        # Entitlement gates: Evaluation/Starter = deterministic only (no LLM).
        # Pro+ may use RuleGenerator / classic AI fallback; Team+ Migration Assistant.
        # Locked AI is always a non-null handle with available=False — never None.
        from app.ai.analyzer import resolve_ai_handle

        ai_enabled, ai_migration_enabled = _org_entitlement_flags(
            session, sim.repository_id
        )
        ai = resolve_ai_handle(enabled=ai_enabled or ai_migration_enabled)

        engine_orm = None
        engine_report = None
        engine_error: str | None = None

        try:
            service = MigrationService(
                session,
                ai=ai if ai_enabled else resolve_ai_handle(enabled=False),
                allow_ai=ai_enabled,
            )
            engine_orm, engine_report = service.run_for_dependency(
                dependency_id=dep.id,
                repository_id=dep.repository_id,
                package_name=dep.package_name,
                from_version=sim.from_version,
                to_version=sim.to_version,
                usages=usages,
                github_url=dep.github_repo_url,
                cve_hints=cve_hints,
                simulation_id=sim.id,
                force_refresh_rules=False,
            )
        except Exception as eng_exc:
            # Never surface raw DB/driver exceptions (e.g. UniqueViolation) to users.
            engine_error = sanitize_engine_error(eng_exc)
            logger.warning(
                "migration_engine_fallback",
                simulation_id=simulation_id,
                error=str(eng_exc)[:500],
                user_safe_error=engine_error,
            )
            session.rollback()
            # Re-load sim after rollback
            sim = session.get(UpgradeSimulation, UUID(simulation_id))
            if sim is None:
                return {"error": "not_found_after_rollback"}
            sim.celery_task_id = self.request.id
            sim.collected_sources = sources

        from app.migration_engine.semantic_index import SemanticASTIndex

        # Semantic AST index is the source of truth for usage sites
        semantic_index = SemanticASTIndex.from_usage_dicts(usages)

        # Classic analyzer only for emergency summary if engine failed entirely —
        # never for inventing patches or replacements. Free plans: deterministic only.
        classic = None
        if engine_report is None:
            analyzer = UpgradeImpactAnalyzer(
                ai=ai if ai_enabled else resolve_ai_handle(enabled=False),
                allow_ai=ai_enabled,
            )
            classic = analyzer.analyze(
                package_name=dep.package_name,
                from_version=sim.from_version,
                to_version=sim.to_version,
                usages=usages,
                sources=sources,
                cve_fixed_hints=cve_hints,
            )

        _set_progress(
            session,
            sim,
            SimulationStatus.GENERATING_PLAN.value,
            55,
            "building_plan",
        )

        annotations = {}
        if engine_report is not None:
            annotations = rule_annotations_by_file(engine_report.matched_usages)
        ast_files = build_ast_affected_files(
            semantic_index.to_usage_dicts(),
            rule_annotations=annotations,
        )

        # Deterministic upgrade-impact layer (catalog rules × AST evidence).
        # Distinct from app.ai.upgrade_simulator.UpgradeImpactAnalyzer (classic/AI).
        from app.services.upgrade_impact import (
            UpgradeImpactAnalyzer as DeterministicUpgradeImpactAnalyzer,
        )

        impact = DeterministicUpgradeImpactAnalyzer().analyze(
            package_name=dep.package_name,
            current_version=sim.from_version or "",
            target_version=sim.to_version or "",
            usages=usages,
            extra_rules=(
                [m.rule for m in engine_report.matched_usages]
                if engine_report and engine_report.matched_usages
                else None
            ),
        )
        impact_payload = impact.to_simulation_payload()

        _set_progress(
            session,
            sim,
            SimulationStatus.ANALYZING_IMPACT.value,
            62,
            "filling_categories",
        )

        graph_neighbors: list[str] = []
        try:
            from app.models.dependency_relationship import DependencyRelationship

            rels = (
                session.execute(
                    select(DependencyRelationship.child_dependency_id).where(
                        DependencyRelationship.parent_dependency_id == dep.id
                    )
                )
                .scalars()
                .all()
            )
            if rels:
                kids = (
                    session.execute(select(Dependency).where(Dependency.id.in_(list(rels))))
                    .scalars()
                    .all()
                )
                graph_neighbors = [k.package_name for k in kids if k.package_name]
        except Exception:  # noqa: BLE001
            graph_neighbors = []

        from app.services.upgrade_intelligence import DynamicUpgradeIntelligence
        from app.services.upgrade_intelligence.simulator_contract import (
            INTELLIGENCE_SCHEMA_VERSION,
            apply_intelligence_to_simulator_findings,
            simulator_confidence,
            simulator_summary,
        )

        try:
            intelligence = DynamicUpgradeIntelligence().analyze(
                package_name=dep.package_name,
                current_version=sim.from_version or "",
                target_version=sim.to_version or "",
                usages=usages,
                ecosystem=dep.ecosystem or "PyPI",
                allow_ai=bool(ai_enabled),
                ai=ai if ai_enabled else None,
                github_url=dep.github_repo_url,
                evidence=evidence_bundle,
                impact=impact,
                skip_network=True,
                latest_version=dep.latest_version,
                graph_neighbors=graph_neighbors,
                cve_hints=cve_hints,
                repository_id=str(dep.repository_id),
                dependency_id=str(dep.id),
            )
            intelligence.timings = {
                **(intelligence.timings or {}),
                "evidence_seconds": evidence_seconds,
            }
        except Exception as intel_exc:  # noqa: BLE001
            logger.warning(
                "dynamic_intelligence_failed",
                simulation_id=simulation_id,
                error=str(intel_exc)[:400],
            )
            intelligence = DynamicUpgradeIntelligence().analyze(
                package_name=dep.package_name,
                current_version=sim.from_version or "",
                target_version=sim.to_version or "",
                usages=usages,
                ecosystem=dep.ecosystem or "PyPI",
                allow_ai=False,
                evidence=evidence_bundle,
                impact=impact,
                skip_network=True,
                latest_version=dep.latest_version,
            )
            intelligence.degradation.append("ai_unavailable")
        intel_overlay = intelligence.to_simulation_overlay()

        from sqlalchemy import delete as sql_delete

        from app.models.upgrade_finding import UpgradeFinding

        session.execute(
            sql_delete(UpgradeFinding).where(UpgradeFinding.simulation_id == sim.id)
        )
        for finding in impact.findings:
            session.add(
                UpgradeFinding(
                    simulation_id=sim.id,
                    dependency_id=dep.id,
                    repository_id=dep.repository_id,
                    package_name=finding.dependency,
                    current_version=finding.current_version,
                    target_version=finding.target_version,
                    change_type=finding.change_type,
                    affected_api=finding.affected_api,
                    description=finding.description,
                    affected_files=finding.affected_files,
                    evidence=[e.model_dump() for e in finding.evidence],
                    confidence=finding.confidence,
                    analysis_source=finding.analysis_source,
                    official_reference=finding.official_reference,
                    is_breaking=finding.is_breaking,
                )
            )
        session.flush()

        # Breaking / deprecated: prefer evidence-rich impact findings; fall back to engine matches
        if impact.breaking_findings or impact.findings:
            breaking = impact_payload["breaking_apis"]
            deprecated = impact_payload["deprecated_apis"]
            if impact.affected_files:
                ast_files = impact.affected_files
        elif engine_report and engine_report.matched_usages:
            breaking = [
                {
                    "symbol": m.rule.symbol,
                    "fully_qualified_name": m.fully_qualified_name,
                    "severity": m.rule.severity,
                    "reason": m.rule.description,
                    "replacement": m.rule.after,  # may be null — never invented
                    "confidence": m.match_confidence,
                    "kind": m.rule.kind,
                    "official_reference": m.rule.official_reference,
                    "analysis_source": "deterministic",
                }
                for m in engine_report.matched_usages
                if m.rule.kind
                in {"removed", "behavior_change", "signature_change", "renamed"}
            ]
            deprecated = [
                {
                    "symbol": m.rule.symbol,
                    "fully_qualified_name": m.fully_qualified_name,
                    "reason": m.rule.description,
                    "replacement": m.rule.after,
                    "confidence": m.match_confidence,
                    "official_reference": m.rule.official_reference,
                    "analysis_source": "deterministic",
                }
                for m in engine_report.matched_usages
                if m.rule.kind == "deprecated"
            ]
        else:
            breaking = []
            deprecated = []

        def _brk_key(row: dict[str, Any]) -> tuple[str, str]:
            return (
                str(row.get("symbol") or row.get("api") or row.get("fully_qualified_name") or "").lower(),
                str(row.get("kind") or row.get("change_type") or ""),
            )

        existing_breaking = {_brk_key(b): b for b in breaking}
        for row in intel_overlay.get("breaking_apis") or []:
            key = _brk_key(row)
            if key in existing_breaking:
                current = existing_breaking[key]
                if current.get("analysis_source") == "deterministic" and row.get("analysis_source") in {
                    "ai",
                    "deterministic+ai",
                }:
                    current["analysis_source"] = "deterministic+ai"
                continue
            breaking.append(row)
        existing_dep = {
            str(d.get("symbol") or d.get("fully_qualified_name") or "").lower() for d in deprecated
        }
        for row in intel_overlay.get("deprecated_apis") or []:
            sym = str(row.get("symbol") or row.get("fully_qualified_name") or "").lower()
            if sym and sym not in existing_dep:
                deprecated.append(row)
                existing_dep.add(sym)

        # Findings: ONLY from migration engine (Pipeline B) — never security docs
        suggested_changes: list[dict[str, Any]] = []
        _set_progress(
            session,
            sim,
            SimulationStatus.GENERATING_PLAN.value,
            72,
            "generating_suggestions",
        )
        auto_fixes: list[str] = []
        manual_work: list[str] = []

        if engine_report and getattr(engine_report, "findings", None):
            suggested_changes = findings_to_suggested_changes(engine_report.findings)
            for finding in suggested_changes:
                if finding.get("migration_status") == "automatic_migration":
                    auto_fixes.append(finding.get("symbol") or finding.get("file_path") or "")
                elif finding.get("migration_status") == "manual_review_required":
                    manual_work.append(
                        f"Manual: {finding.get('symbol') or finding.get('file_path')} — "
                        f"{finding.get('status_detail') or finding.get('explanation') or 'review required'}"
                    )
        elif engine_report and engine_report.patches:
            for p in engine_report.patches:
                high_conf = (
                    p.auto_fixable
                    and p.confidence >= 0.75
                    and bool(p.suggested_code)
                    and p.validation_status == "validated"
                    and code_differs(p.current_code, p.suggested_code)
                )
                finding = build_migration_finding(
                    file_path=p.file_path,
                    line=p.line,
                    symbol=p.symbol,
                    current_code=p.current_code,
                    suggested_code=p.suggested_code if high_conf else None,
                    explanation=p.reason
                    or (
                        "Automatic replacement from matched migration rule."
                        if high_conf
                        else "Unknown or incomplete rule replacement — Manual review required."
                    ),
                    confidence=p.confidence,
                    automatic=high_conf,
                    official_reference=p.official_reference,
                    validation_status="validated" if high_conf else (p.validation_status or "needs_review"),
                    unified_diff=p.unified_diff if high_conf else None,
                    risk_flagged=not high_conf,
                )
                if finding["migration_status"] == "automatic_migration":
                    auto_fixes.append(p.symbol or p.file_path)
                elif finding["migration_status"] == "manual_review_required":
                    manual_work.append(
                        f"Manual: {p.symbol or p.file_path} — {finding.get('status_detail') or 'review required'}"
                    )
                suggested_changes.append(finding)
        elif engine_error:
            # Never disguise engine failures as "no rules available".
            suggested_changes.append(
                build_migration_finding(
                    file_path="(repository)",
                    line=None,
                    symbol=dep.package_name,
                    current_code="",
                    suggested_code=None,
                    explanation=(
                        "Migration engine failed before patches could be generated. "
                        f"Error: {engine_error}"
                    ),
                    confidence=0.2,
                    automatic=False,
                    official_reference=(dep.pypi_url or dep.github_repo_url),
                    risk_flagged=True,
                )
            )
            manual_work.append(f"Migration engine error — {engine_error}")
        elif not (engine_report and engine_report.rules):
            # Catalog-missing Unknown is produced by the engine for patch generation.
            # The simulator contract remaps it after Dynamic Intelligence runs.
            pass

        suggested_changes = apply_intelligence_to_simulator_findings(
            suggested_changes,
            intelligence,
            package_name=dep.package_name,
        )
        auto_fixes = [
            f.get("symbol") or f.get("file_path") or ""
            for f in suggested_changes
            if f.get("migration_status") == "automatic_migration"
        ]
        manual_work = [
            f"Manual: {f.get('symbol') or f.get('file_path')} — "
            f"{f.get('status_detail') or f.get('explanation') or 'review required'}"
            for f in suggested_changes
            if f.get("migration_status") in {"manual_review_required", "unresolved"}
        ]

        # ------------------------------------------------------------------
        # Team+ AI Migration Assistant — LLM patches grounded in engine context
        # Evaluation/Starter/Pro never enqueue or execute this stage.
        # ------------------------------------------------------------------
        ai_assistant_error: str | None = None
        if (
            ai_migration_enabled
            and ai is not None
            and engine_report is not None
            and not _is_simulation_cancelled(session, simulation_id)
        ):
            _set_progress(
                session,
                sim,
                SimulationStatus.GENERATING_PLAN.value,
                80,
                "ai_migration_assistant",
            )
            try:
                from app.migration_engine.ai_patch_assistant import (
                    AIMigrationPatchAssistant,
                    merge_assistant_with_deterministic,
                )

                docs = []
                releases = []
                if isinstance(sources, dict):
                    docs = list(sources.get("documentation") or sources.get("docs") or [])[:6]
                    releases = list(sources.get("github_releases") or sources.get("release_notes") or [])[
                        :8
                    ]
                ai_patches, ai_assistant_error = AIMigrationPatchAssistant(ai=ai).generate(
                    package_name=dep.package_name,
                    from_version=sim.from_version,
                    to_version=sim.to_version,
                    usages=usages,
                    rules=engine_report.rules,
                    official_references=list(engine_report.official_references or []),
                    documentation_excerpts=docs,
                    release_notes=releases,
                    deterministic_findings=suggested_changes,
                )
                if ai_patches:
                    suggested_changes = merge_assistant_with_deterministic(
                        suggested_changes, ai_patches
                    )
                    suggested_changes = apply_intelligence_to_simulator_findings(
                        suggested_changes,
                        intelligence,
                        package_name=dep.package_name,
                    )
                    auto_fixes = [
                        f.get("symbol") or f.get("file_path") or ""
                        for f in suggested_changes
                        if f.get("migration_status") == "automatic_migration"
                    ]
                    manual_work = [
                        f"Manual: {f.get('symbol') or f.get('file_path')} — "
                        f"{f.get('status_detail') or f.get('explanation') or 'review required'}"
                        for f in suggested_changes
                        if f.get("migration_status") in {"manual_review_required", "unresolved"}
                    ]
            except Exception as ai_exc:  # noqa: BLE001
                ai_assistant_error = str(ai_exc)[:500]
                logger.warning(
                    "ai_migration_assistant_failed",
                    simulation_id=simulation_id,
                    error=ai_assistant_error,
                )

        scoring = engine_report.scoring if engine_report else None
        if scoring:
            readiness = scoring.readiness_score
            risk = scoring.risk_score
            conf = scoring.confidence
            hours = scoring.migration_time_hours
        elif classic is not None:
            readiness = classic.readiness_score
            risk = classic.risk_score
            conf = classic.confidence
            hours = classic.migration_time_hours
        else:
            readiness, risk, conf, hours = 70.0, 30.0, 0.4, 2.0

        rules_dump = (
            [r.model_dump() for r in engine_report.rules] if engine_report else []
        )
        if not rules_dump and intelligence.migration_rules:
            rules_dump = list(intelligence.migration_rules)
        refs = collect_official_references(
            package_name=dep.package_name,
            pypi_url=dep.pypi_url,
            github_url=dep.github_repo_url,
            home_page=dep.home_page,
            engine_refs=(
                [i.model_dump() for i in engine_report.official_reference_items]
                if engine_report and engine_report.official_reference_items
                else (engine_report.official_references if engine_report else None)
            ),
            sources=sources,
        )

        if engine_report is not None:
            summary = engine_report.summary
            plan = engine_report.migration_plan
            security = engine_report.security_improvements or []
            performance = engine_report.performance_improvements or []
        elif classic is not None:
            summary = classic.summary
            plan = [p.model_dump() for p in classic.migration_plan]
            security = classic.security_improvements
            performance = classic.performance_improvements
        else:
            summary = (
                f"Upgrade analysis for {dep.package_name} {sim.from_version} → {sim.to_version}."
            )
            plan = []
            security = cve_hints[:10]
            performance = []

        if engine_error:
            summary = f"{summary} Migration engine error: {engine_error}"
        catalog_matched = bool(engine_report and engine_report.rules)
        if impact.breaking_findings or impact.catalog_rules_applied:
            summary = impact.summary
        summary = simulator_summary(
            intelligence,
            engine_summary=summary,
            catalog_matched=catalog_matched,
        )
        # AI failures stay in collected_sources / intelligence.degradation — never alter verdict with catalog-Unknown.

        conf = simulator_confidence(
            intelligence,
            engine_confidence=conf,
            catalog_matched=catalog_matched,
        )
        cls = intelligence.breaking_classification
        if cls == "breaking":
            risk = max(risk, 75.0)
            readiness = min(readiness, 40.0)
        elif cls == "potentially_breaking":
            risk = max(risk, 55.0)
            readiness = min(readiness, 55.0)
        elif cls == "safe":
            risk = min(risk, 25.0)

        auto_count = len(auto_fixes)
        manual_count = len(manual_work) or (
            scoring.manual_fix_count if scoring else len(manual_work)
        )
        if not manual_work and classic is not None and classic.manual_work_required:
            manual_work = list(classic.manual_work_required)

        sources["migration_engine_report_id"] = str(engine_orm.id) if engine_orm else None
        sources["rules_count"] = len(rules_dump)
        sources["official_references"] = refs
        sources["engine_error"] = engine_error
        sources["ai_migration_enabled"] = ai_migration_enabled
        sources["ai_assistant_error"] = ai_assistant_error
        sources["confidence_label"] = confidence_label(conf)
        sources["dynamic_intelligence"] = intelligence.model_dump()
        sources["breaking_classification"] = intelligence.breaking_classification
        sources["analysis_method"] = intelligence.analysis_method
        sources["ai_invoked"] = intelligence.ai_invoked
        sources["ai_skipped_reason"] = intelligence.ai_skipped_reason
        sources["intelligence_schema_version"] = INTELLIGENCE_SCHEMA_VERSION
        sim.collected_sources = sources

        sim.summary = summary
        ai_incomplete = intelligence.ai_skipped_reason in {
            "ai_unavailable",
            "ai_timeout",
            "ai_rate_limited",
        } or any(
            flag in (intelligence.degradation or [])
            for flag in (
                "ai_unavailable",
                "ai_timeout",
                "ai_rate_limited",
                "ai_completion_failed",
                "malformed_ai_response",
            )
        )
        if not catalog_matched and ai_incomplete:
            # Empty catalog + failed AI is not a clean-upgrade score from unmatched rules.
            readiness = min(float(readiness or 0.0), 55.0)
            risk = max(float(risk or 0.0), 45.0)
            conf = min(float(conf or 0.0), 0.5)
        sim.safe_to_upgrade = (
            readiness >= 70
            and risk <= 40
            and not breaking
            and intelligence.breaking_classification in {"safe", "low_risk"}
            and not ai_incomplete
        )
        sim.confidence = conf
        sim.readiness_score = readiness
        sim.risk_score = risk
        sim.migration_time_hours = hours
        sim.migration_time_label = f"~{hours} hours"
        sim.breaking_apis = breaking
        sim.deprecated_apis = deprecated
        sim.affected_files = ast_files
        sim.affected_symbols = sorted(
            {
                u.get("fully_qualified_name")
                for u in usages
                if u.get("fully_qualified_name")
            }
        )
        sim.affected_functions = sorted(
            {
                u.get("enclosing_function")
                for u in usages
                if u.get("enclosing_function")
            }
        )
        sim.affected_classes = sorted(
            {u.get("enclosing_class") for u in usages if u.get("enclosing_class")}
        )
        sim.security_improvements = security
        sim.performance_improvements = performance
        sim.manual_work_required = manual_work[:30]
        sim.automatic_fixes_possible = auto_fixes
        sim.migration_plan = plan
        sim.suggested_changes = suggested_changes
        base_factors = {}
        if classic is not None:
            base_factors = (
                classic.readiness_factors.model_dump()
                if hasattr(classic.readiness_factors, "model_dump")
                else dict(classic.readiness_factors or {})
            )
        elif scoring is not None:
            base_factors = {
                "breaking_apis": max(0.0, 100.0 - scoring.breakdown.get("breaking_matches", 0) * 15),
                "deprecated_calls": max(0.0, 100.0 - scoring.breakdown.get("deprecated_matches", 0) * 10),
                "security": scoring.security_improvement,
                "tests": 50.0,
            }
        sim.readiness_factors = {
            **base_factors,
            "auto_fix_count": auto_count,
            "manual_fix_count": manual_count,
            "rules_total": len(rules_dump),
            "ast_usage_sites": len(usages),
            "ast_files": len(ast_files),
            "semantic_index_sites": len(usages),
        }
        if engine_error:
            confidence_reason = f"Migration engine failed: {engine_error}"
        elif rules_dump:
            confidence_reason = (
                "Deterministic semantic AST × migration rule match confidence."
                + (
                    " AI Migration Assistant enriched patches."
                    if ai_migration_enabled and not ai_assistant_error
                    else ""
                )
            )
        else:
            confidence_reason = (
                "No structured migration rules for this version range; manual review required."
            )
        sim.raw_ai_response = {
            "engine": "deterministic_semantic_matcher",
            "report_id": str(engine_orm.id) if engine_orm else None,
            "rules": rules_dump,
            "official_references": refs,
            "scoring": scoring.model_dump() if scoring else None,
            "classic": classic.model_dump() if classic is not None else None,
            "engine_error": engine_error,
            "ai_migration_enabled": ai_migration_enabled,
            "ai_assistant_error": ai_assistant_error,
            "confidence_label": confidence_label(conf),
            "confidence_reason": confidence_reason,
            "upgrade_impact": impact.model_dump(),
            "unresolved_apis": impact.unresolved_apis,
            "analysis_source": intelligence.analysis_method,
            "dynamic_intelligence": intelligence.model_dump(),
            "breaking_classification": intelligence.breaking_classification,
        }
        if engine_error:
            sim.model_used = (
                f"fallback+{ai.model}" if ai.available else "fallback+heuristic"
            )
        elif ai_migration_enabled and not ai_assistant_error and ai.available:
            sim.model_used = f"semantic_matcher+ai_migration:{ai.model}"
        elif ai.available:
            sim.model_used = f"dynamic_intelligence+{ai.model}"
        else:
            sim.model_used = "dynamic_intelligence+deterministic"

        _set_progress(session, sim, SimulationStatus.SCORING.value, 90, "calculating_confidence")

        if _is_simulation_cancelled(session, simulation_id):
            return {"simulation_id": simulation_id, "status": "cancelled"}

        completed = _utcnow()
        sim.status = SimulationStatus.COMPLETED.value
        sim.progress_percent = 100
        sim.current_stage = "completed"
        sim.completed_at = completed
        sim.last_heartbeat_at = completed
        sim.stage_timings = close_stage_timings(sim.stage_timings, now=completed)
        if sim.started_at:
            sim.duration_seconds = (completed - sim.started_at).total_seconds()

        # Enrich usage metering for billing analytics (Upgrade Simulator = Pro+)
        try:
            from app.models.billing import FeatureUsageEvent

            usage = (
                session.execute(
                    select(FeatureUsageEvent)
                    .where(FeatureUsageEvent.simulation_id == sim.id)
                    .order_by(FeatureUsageEvent.created_at.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )
            duration_ms = int((sim.duration_seconds or 0) * 1000)
            # Heuristic metering until provider token accounting is wired end-to-end
            tokens = max(800, int((duration_ms / 1000.0) * 120))
            cost = round(tokens * 0.000002, 6)
            usage_feature = (
                "ai_migration_assistant"
                if ai_migration_enabled and not engine_error
                else "upgrade_simulator"
            )
            if usage:
                usage.feature = usage_feature
                usage.execution_time_ms = duration_ms
                usage.tokens_used = tokens
                usage.estimated_cost_usd = cost
                meta = dict(usage.extra_metadata or {})
                meta.update(
                    {
                        "package_name": sim.package_name,
                        "from_version": sim.from_version,
                        "to_version": sim.to_version,
                        "model_used": sim.model_used,
                        "ai_migration_enabled": ai_migration_enabled,
                        "ai_assistant_error": ai_assistant_error,
                        "engine_error": engine_error,
                    }
                )
                usage.extra_metadata = meta
            else:
                from app.models.repository import Repository
                from app.services.entitlements import record_feature_usage_sync

                repo = session.get(Repository, sim.repository_id)
                if repo and repo.organization_id and sim.triggered_by_user_id:
                    record_feature_usage_sync(
                        session,
                        organization_id=repo.organization_id,
                        user_id=sim.triggered_by_user_id,
                        feature=usage_feature,
                        repository_id=sim.repository_id,
                        dependency_id=sim.dependency_id,
                        simulation_id=sim.id,
                        tokens_used=tokens,
                        estimated_cost_usd=cost,
                        execution_time_ms=duration_ms,
                        meta={
                            "package_name": sim.package_name,
                            "from_version": sim.from_version,
                            "to_version": sim.to_version,
                            "model_used": sim.model_used,
                        },
                    )
        except Exception:
            logger.exception("upgrade_simulator_usage_metering_failed", simulation_id=simulation_id)

        session.commit()

        logger.info(
            "upgrade_simulation_completed",
            simulation_id=simulation_id,
            readiness=sim.readiness_score,
            risk=sim.risk_score,
            affected_files=len(ast_files),
            engine_report_id=str(engine_orm.id) if engine_orm else None,
        )
        return {
            "simulation_id": simulation_id,
            "status": "completed",
            "readiness_score": sim.readiness_score,
            "safe_to_upgrade": sim.safe_to_upgrade,
            "engine_report_id": str(engine_orm.id) if engine_orm else None,
            "affected_files": len(ast_files),
        }

    except Exception as exc:
        session.rollback()
        logger.exception("upgrade_simulation_failed", simulation_id=simulation_id, error=str(exc))
        try:
            sim = session.get(UpgradeSimulation, UUID(simulation_id))
            if sim:
                now = _utcnow()
                sim.status = SimulationStatus.FAILED.value
                sim.error_message = str(exc)[:2000]
                sim.current_stage = "failed"
                sim.completed_at = now
                sim.last_heartbeat_at = now
                sim.stage_timings = close_stage_timings(sim.stage_timings, now=now)
                if sim.started_at and sim.duration_seconds is None:
                    sim.duration_seconds = (now - sim.started_at).total_seconds()
                session.commit()
        except Exception:
            session.rollback()
        raise
    finally:
        session.close()


def _org_entitlement_flags(session, repository_id: UUID) -> tuple[bool, bool]:
    """Return (ai_enabled, can_generate_ai_migration) for the repository's org."""
    try:
        from app.models.billing import Subscription
        from app.models.organization import Organization
        from app.models.repository import Repository
        from app.services.entitlements import resolve_entitlements

        repo = session.get(Repository, repository_id)
        if repo is None or repo.organization_id is None:
            return False, False
        org = session.get(Organization, repo.organization_id)
        if org is None:
            return False, False
        sub = (
            session.execute(
                select(Subscription).where(Subscription.organization_id == org.id)
            )
            .scalars()
            .first()
        )
        ents = resolve_entitlements(org, sub)
        return bool(ents.ai_enabled), bool(ents.can_generate_ai_migration)
    except Exception as exc:  # noqa: BLE001
        logger.warning("sim_entitlement_check_failed", error=str(exc)[:300])
        return False, False


def _org_ai_enabled(session, repository_id: UUID) -> bool:
    """Pro+ gate for LLM use inside Upgrade Simulator (rule learning / classic fallback)."""
    return _org_entitlement_flags(session, repository_id)[0]


def _org_can_ai_migration(session, repository_id: UUID) -> bool:
    """Team/Enterprise entitlement check for AI Migration Assistant (sync worker)."""
    return _org_entitlement_flags(session, repository_id)[1]


def create_simulation_record(
    session,
    *,
    dependency: Dependency,
    user_id: UUID | None,
    from_version: str,
    to_version: str,
    force_refresh: bool = False,
) -> tuple[UpgradeSimulation, bool]:
    """
    Create or reuse a cached completed simulation.
    Returns (simulation, created_new).
    """
    usages = (
        session.execute(
            select(LibraryUsage).where(LibraryUsage.dependency_id == dependency.id)
        )
        .scalars()
        .all()
    )
    usage_dicts = [
        {
            "fully_qualified_name": u.fully_qualified_name,
            "file_path": u.file_path,
            "line": u.line,
        }
        for u in usages
    ]
    fp = usage_fingerprint(usage_dicts)
    cache_key = build_cache_key(str(dependency.id), from_version, to_version, fp)

    if not force_refresh:
        existing = session.execute(
            select(UpgradeSimulation)
            .where(
                UpgradeSimulation.dependency_id == dependency.id,
                UpgradeSimulation.cache_key == cache_key,
                UpgradeSimulation.status == SimulationStatus.COMPLETED.value,
            )
            .order_by(UpgradeSimulation.completed_at.desc())
        ).scalars().first()
        if existing:
            from app.services.upgrade_intelligence.simulator_contract import (
                cached_simulation_is_current,
            )

            if cached_simulation_is_current(existing):
                return existing, False
            # Stale pre-intelligence rows are kept for history; a fresh analysis is created.

        # Reuse in-flight simulation for same key
        inflight = session.execute(
            select(UpgradeSimulation).where(
                UpgradeSimulation.dependency_id == dependency.id,
                UpgradeSimulation.cache_key == cache_key,
                UpgradeSimulation.status.in_(
                    [
                        SimulationStatus.PENDING.value,
                        SimulationStatus.QUEUED.value,
                        SimulationStatus.COLLECTING_SOURCES.value,
                        SimulationStatus.ANALYZING_IMPACT.value,
                        SimulationStatus.GENERATING_PLAN.value,
                        SimulationStatus.SCORING.value,
                    ]
                ),
            )
        ).scalars().first()
        if inflight:
            return inflight, False

    sim = UpgradeSimulation(
        dependency_id=dependency.id,
        repository_id=dependency.repository_id,
        triggered_by_user_id=user_id,
        package_name=dependency.package_name,
        from_version=from_version,
        to_version=to_version,
        status=SimulationStatus.QUEUED.value,
        progress_percent=0,
        current_stage="queued",
        cache_key=cache_key,
        queued_at=_utcnow(),
        stage_timings=[],
    )
    session.add(sim)
    session.flush()
    return sim, True
