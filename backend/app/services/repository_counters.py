"""Recompute denormalized repository counters from dependency rows."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

from sqlalchemy import select

from app.core.enums import LicensePolicyAction
from app.models.dependency import Dependency
from app.models.repository import Repository


def apply_repository_counters_from_dependencies(
    repo: Repository,
    deps: Sequence[Dependency],
) -> None:
    """
    Align repository aggregate counters with the current dependency rows.

    Used when a scan ends before the normal completion aggregation
    (cancel / failure) so UI counts cannot drift from stored dependencies.
    """
    dependency_count = len(deps)
    outdated_count = sum(1 for d in deps if d.is_outdated)
    vulnerable_count = sum(1 for d in deps if d.has_vulnerabilities)
    license_issues = sum(
        1
        for d in deps
        if d.license_policy_action == LicensePolicyAction.REJECT.value
    )
    critical_alert_count = sum(1 for d in deps if (d.critical_vuln_count or 0) > 0)
    health_scores = [d.health_score for d in deps if d.health_score is not None]
    avg_health: Optional[float] = (
        round(sum(health_scores) / len(health_scores), 1) if health_scores else None
    )

    repo.dependency_count = dependency_count
    repo.outdated_count = outdated_count
    repo.vulnerable_count = vulnerable_count
    repo.license_issues_count = license_issues
    repo.critical_alert_count = critical_alert_count
    repo.warning_count = license_issues + outdated_count
    repo.health_score = avg_health


def sync_repository_counters(session, repo: Repository) -> None:
    """Load dependencies for ``repo`` and apply aggregate counters (sync session)."""
    deps = (
        session.execute(select(Dependency).where(Dependency.repository_id == repo.id))
        .scalars()
        .all()
    )
    apply_repository_counters_from_dependencies(repo, deps)


async def async_sync_repository_counters(db, repo: Repository) -> None:
    """Load dependencies for ``repo`` and apply aggregate counters (async session)."""
    deps = (
        await db.execute(select(Dependency).where(Dependency.repository_id == repo.id))
    ).scalars().all()
    apply_repository_counters_from_dependencies(repo, deps)
