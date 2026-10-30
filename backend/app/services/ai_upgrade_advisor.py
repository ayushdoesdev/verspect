"""AI Upgrade Advisor — enrichment only.

Consumes persisted deterministic repository intelligence (versions, CVEs,
health, usage). Never recomputes or rediscovers that data.

This module holds the AI pipeline formerly embedded in Repository Scan.
Callers: Celery `run_ai_upgrade_advisor` and on-demand refresh paths.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.analyzer import AIAnalyzer
from app.core.logging import get_logger
from app.models.dependency import Dependency
from app.models.library_usage import LibraryUsage
from app.models.release import Release

logger = get_logger(__name__)

ProgressFn = Callable[[str, int], None]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_release_stub(session: Session, dep: Dependency) -> Optional[Release]:
    """Persist deterministic release metadata without AI (scan-time)."""
    if not dep.is_outdated or not dep.current_version or not dep.latest_version:
        return None
    existing = session.execute(
        select(Release).where(
            Release.dependency_id == dep.id,
            Release.version == dep.latest_version,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    release = Release(
        dependency_id=dep.id,
        package_name=dep.package_name,
        version=dep.latest_version,
        previous_version=dep.current_version,
        is_major=dep.major_behind > 0,
        is_minor=dep.major_behind == 0 and dep.minor_behind > 0,
        is_patch=dep.major_behind == 0 and dep.minor_behind == 0 and dep.patch_behind > 0,
        released_at=dep.last_release_at,
    )
    session.add(release)
    session.flush()
    return release


def analyze_release_with_ai(
    session: Session,
    dep: Dependency,
    ai: AIAnalyzer,
    *,
    release_notes: str = "",
) -> None:
    """Reuse existing AIAnalyzer.analyze_release_notes — fill Release AI fields."""
    if not dep.current_version or not dep.latest_version:
        return
    existing = session.execute(
        select(Release).where(
            Release.dependency_id == dep.id,
            Release.version == dep.latest_version,
        )
    ).scalar_one_or_none()
    if existing and existing.ai_summary:
        return

    used_symbols = [
        u.fully_qualified_name
        for u in session.execute(
            select(LibraryUsage).where(LibraryUsage.dependency_id == dep.id).limit(100)
        )
        .scalars()
        .all()
    ]
    analysis = ai.analyze_release_notes(
        dep.package_name,
        dep.current_version,
        dep.latest_version,
        (release_notes or "")[:12000],
        used_symbols,
    )
    affected_files = list(
        {
            u.file_path
            for u in session.execute(
                select(LibraryUsage).where(LibraryUsage.dependency_id == dep.id)
            )
            .scalars()
            .all()
        }
    )
    if existing is None:
        existing = Release(
            dependency_id=dep.id,
            package_name=dep.package_name,
            version=dep.latest_version,
            previous_version=dep.current_version,
            is_major=dep.major_behind > 0,
            is_minor=dep.major_behind == 0 and dep.minor_behind > 0,
            is_patch=dep.major_behind == 0 and dep.minor_behind == 0 and dep.patch_behind > 0,
            released_at=dep.last_release_at,
            release_notes_raw=release_notes[:20000] if release_notes else None,
        )
        session.add(existing)
        session.flush()

    existing.ai_summary = analysis.get("ai_summary")
    existing.breaking_changes = analysis.get("breaking_changes")
    existing.deprecated_apis = analysis.get("deprecated_apis")
    existing.new_features = analysis.get("new_features")
    existing.bug_fixes = analysis.get("bug_fixes")
    existing.migration_difficulty = analysis.get("migration_difficulty")
    existing.risk_score = analysis.get("risk_score")
    existing.affected_symbols = analysis.get("affected_symbols")
    existing.affected_files_in_repo = affected_files
    existing.has_breaking_changes = bool(
        analysis.get("has_breaking_changes") or analysis.get("breaking_changes")
    )
    existing.ai_analyzed_at = _utcnow()
    if release_notes and not existing.release_notes_raw:
        existing.release_notes_raw = release_notes[:20000]


def explain_dependency_with_ai(
    session: Session,
    dep: Dependency,
    ai: AIAnalyzer,
) -> dict[str, Any]:
    """Reuse existing AIAnalyzer.explain_dependency — persist advisor fields."""
    used_symbols = [
        u.fully_qualified_name
        for u in session.execute(
            select(LibraryUsage)
            .where(LibraryUsage.dependency_id == dep.id)
            .limit(12)
        )
        .scalars()
        .all()
    ]
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
    dep.ai_generated_at = _utcnow()
    return explanation


def run_ai_upgrade_advisor_for_repository(
    session: Session,
    repository_id: UUID,
    *,
    ai: Optional[AIAnalyzer] = None,
    on_progress: Optional[ProgressFn] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> dict[str, Any]:
    """
    Run the full AI Upgrade Advisor over persisted dependencies.

    Reads only deterministic fields already written by Repository Scan.
    """
    ai = ai or AIAnalyzer()
    deps = (
        session.execute(
            select(Dependency)
            .where(Dependency.repository_id == repository_id)
            .order_by(Dependency.package_name.asc())
        )
        .scalars()
        .all()
    )
    total = len(deps)
    if on_progress:
        on_progress("preparing", 10)

    processed = 0
    for dep in deps:
        if should_cancel and should_cancel():
            return {"status": "cancelled", "processed": processed, "total": total}

        if on_progress and total:
            # 10–85% while analyzing deps
            pct = 10 + int(75 * processed / max(total, 1))
            stage = "analyzing" if processed < total * 0.7 else "generating"
            on_progress(stage, min(85, pct))

        try:
            if dep.is_outdated and dep.current_version and dep.latest_version:
                analyze_release_with_ai(session, dep, ai)
            explain_dependency_with_ai(session, dep, ai)
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            logger.warning(
                "ai_advisor_dep_failed",
                dependency_id=str(dep.id),
                package=dep.package_name,
                error=str(exc),
            )
            # Continue remaining deps — partial enrichment is OK

        processed += 1

    if on_progress:
        on_progress("saving", 92)
    return {"status": "completed", "processed": processed, "total": total}


def org_supports_ai_advisor(session: Session, repository_id: UUID) -> bool:
    """Pro+ with active write entitlements may run AI Upgrade Advisor."""
    from app.models.billing import Subscription
    from app.models.organization import Organization
    from app.models.repository import Repository
    from app.services.entitlements import resolve_entitlements

    repo = session.get(Repository, repository_id)
    if repo is None or not repo.organization_id:
        return False
    org = session.get(Organization, repo.organization_id)
    if org is None:
        return False
    sub = (
        session.execute(
            select(Subscription).where(Subscription.organization_id == org.id)
        )
        .scalars()
        .first()
    )
    ents = resolve_entitlements(org, sub)
    return bool(ents.ai_enabled and ents.can_write)
