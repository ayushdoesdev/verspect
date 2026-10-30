"""Celery tasks — on-demand AI analysis."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.ai.analyzer import AIAnalyzer
from app.core.celery_app import celery_app
from app.core.database import SyncSessionLocal
from app.core.logging import get_logger
from app.core.mixins import utcnow
from app.models.dependency import Dependency
from app.models.library_usage import LibraryUsage
from app.models.migration import MigrationReport
from app.scanners.alternatives import AlternativeEngine
from app.scanners.normalize import normalize_package_name
from app.models.alternative import AlternativeLibrary
from sqlalchemy import delete

logger = get_logger(__name__)


@celery_app.task(name="app.services.tasks.analysis_tasks.analyze_dependency_ai")
def analyze_dependency_ai(dependency_id: str) -> dict[str, Any]:
    session = SyncSessionLocal()
    try:
        dep = session.get(Dependency, UUID(dependency_id))
        if dep is None:
            return {"error": "not_found"}

        usages = (
            session.execute(
                select(LibraryUsage).where(LibraryUsage.dependency_id == dep.id).limit(100)
            )
            .scalars()
            .all()
        )
        used_symbols = [u.fully_qualified_name for u in usages]
        affected_files = sorted({u.file_path for u in usages})

        ai = AIAnalyzer()
        explanation = ai.explain_dependency(
            {
                "package_name": dep.package_name,
                "current_version": dep.current_version,
                "latest_version": dep.latest_version,
                "is_outdated": dep.is_outdated,
                "vulnerability_count": dep.vulnerability_count,
                "license_spdx": dep.license_spdx,
                "health_score": dep.health_score,
                "used_symbols": used_symbols,
                "summary": dep.summary,
            }
        )
        dep.ai_explanation = explanation.get("explanation")
        dep.ai_should_update = explanation.get("should_update")
        dep.ai_security_summary = explanation.get("security_summary")
        dep.ai_generated_at = datetime.now(timezone.utc)

        if dep.current_version and dep.latest_version and dep.is_outdated:
            report_data = ai.generate_migration_report(
                {
                    "package_name": dep.package_name,
                    "from_version": dep.current_version,
                    "to_version": dep.latest_version,
                    "used_symbols": used_symbols,
                    "affected_files": affected_files,
                    "summary": dep.summary,
                    "cve_count": dep.vulnerability_count,
                }
            )
            session.add(
                MigrationReport(
                    dependency_id=dep.id,
                    repository_id=dep.repository_id,
                    from_version=dep.current_version,
                    to_version=dep.latest_version,
                    package_name=dep.package_name,
                    title=report_data.get("title")
                    or f"Migrate {dep.package_name} to {dep.latest_version}",
                    summary=report_data.get("summary") or "",
                    difficulty=report_data.get("difficulty") or "medium",
                    risk_score=float(report_data.get("risk_score") or 50),
                    estimated_effort_hours=report_data.get("estimated_effort_hours"),
                    breaking_changes=report_data.get("breaking_changes"),
                    api_mappings=report_data.get("api_mappings"),
                    affected_files=report_data.get("affected_files") or affected_files,
                    step_by_step=report_data.get("step_by_step"),
                    code_examples=report_data.get("code_examples"),
                    testing_checklist=report_data.get("testing_checklist"),
                    rollback_plan=report_data.get("rollback_plan"),
                    recommendation=report_data.get("recommendation"),
                    should_update=report_data.get("should_update"),
                    generated_at=datetime.now(timezone.utc),
                    model_used=ai.model if ai.available else "fallback",
                )
            )

        # Merge AI alternatives with KB
        engine = AlternativeEngine()
        kb_alts = engine.suggest(dep.package_name)
        ai_alts = ai.suggest_alternatives(
            {
                "package_name": dep.package_name,
                "summary": dep.summary,
                "license_spdx": dep.license_spdx,
                "health_score": dep.health_score,
            }
        )
        session.execute(
            delete(AlternativeLibrary).where(AlternativeLibrary.dependency_id == dep.id)
        )
        rank = 1
        seen: set[str] = set()
        for alt in kb_alts + [
            {
                "package_name": dep.package_name,
                "alternative_name": a.get("alternative_name"),
                "alternative_normalized": normalize_package_name(a.get("alternative_name") or ""),
                "reason": a.get("reason") or "",
                "pros": a.get("pros") or [],
                "cons": a.get("cons") or [],
                "migration_effort": a.get("migration_effort") or "medium",
                "confidence": a.get("confidence"),
                "source": "ai",
                "rank": 0,
            }
            for a in ai_alts
            if a.get("alternative_name")
        ]:
            key = alt["alternative_normalized"]
            if not key or key in seen:
                continue
            seen.add(key)
            session.add(
                AlternativeLibrary(
                    dependency_id=dep.id,
                    package_name=dep.package_name,
                    alternative_name=alt["alternative_name"],
                    alternative_normalized=key,
                    reason=alt["reason"],
                    pros=alt.get("pros"),
                    cons=alt.get("cons"),
                    migration_effort=alt.get("migration_effort") or "medium",
                    rank=rank,
                    confidence=alt.get("confidence"),
                    source=alt.get("source", "ai"),
                    pypi_url=f"https://pypi.org/project/{key}/",
                )
            )
            rank += 1

        session.commit()
        return {"dependency_id": dependency_id, "status": "ok"}
    except Exception as exc:
        session.rollback()
        logger.exception("analyze_dependency_ai_failed", error=str(exc))
        raise
    finally:
        session.close()
