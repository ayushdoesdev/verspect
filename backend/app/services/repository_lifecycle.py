"""Repository lifecycle — archive, pause sync, hard remove with cleanup."""

from __future__ import annotations

from typing import Awaitable, Callable, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import RepositorySyncStatus, ScanStatus, SimulationStatus
from app.core.logging import get_logger
from app.core.mixins import utcnow
from app.models.repository import Repository
from app.models.scan import Scan
from app.models.upgrade_simulation import UpgradeSimulation
from app.models.user import User
from app.services.audit import record_audit_event
from app.services.job_health import as_aware, close_stage_timings

logger = get_logger(__name__)

ACTIVE_SCAN_STATUSES = {
    ScanStatus.PENDING.value,
    ScanStatus.QUEUED.value,
    ScanStatus.RUNNING.value,
    ScanStatus.CLONING.value,
    ScanStatus.CLASSIFYING.value,
    ScanStatus.SCANNING_MANIFESTS.value,
    ScanStatus.PARSING_AST.value,
    ScanStatus.CHECKING_VERSIONS.value,
    ScanStatus.CHECKING_VULNERABILITIES.value,
    ScanStatus.CHECKING_LICENSES.value,
    ScanStatus.SCORING_HEALTH.value,
    ScanStatus.ANALYZING_AI.value,
}

ACTIVE_SIMULATION_STATUSES = {
    SimulationStatus.PENDING.value,
    SimulationStatus.QUEUED.value,
    SimulationStatus.COLLECTING_SOURCES.value,
    SimulationStatus.ANALYZING_IMPACT.value,
    SimulationStatus.GENERATING_PLAN.value,
    SimulationStatus.SCORING.value,
}


async def cancel_active_scans(
    db: AsyncSession,
    repository_id: UUID,
    *,
    reason: str,
) -> int:
    """Cancel in-flight scans and revoke Celery tasks. Returns cancelled count."""
    scans = (
        await db.execute(
            select(Scan).where(
                Scan.repository_id == repository_id,
                Scan.status.in_(ACTIVE_SCAN_STATUSES),
            )
        )
    ).scalars().all()
    count = 0
    for scan in scans:
        await _cancel_scan(db, scan, reason=reason)
        count += 1
    return count


async def cancel_active_simulations(
    db: AsyncSession,
    repository_id: UUID,
    *,
    reason: str,
) -> int:
    sims = (
        await db.execute(
            select(UpgradeSimulation).where(
                UpgradeSimulation.repository_id == repository_id,
                UpgradeSimulation.status.in_(ACTIVE_SIMULATION_STATUSES),
            )
        )
    ).scalars().all()
    count = 0
    now = utcnow()
    for sim in sims:
        if sim.celery_task_id:
            _revoke_celery(sim.celery_task_id)
        sim.cancel_requested = True
        sim.status = SimulationStatus.CANCELLED.value
        sim.current_stage = "cancelled"
        sim.completed_at = now
        sim.error_message = reason
        sim.stage_timings = close_stage_timings(sim.stage_timings, now=now)
        started = as_aware(sim.started_at)
        if started and sim.duration_seconds is None:
            sim.duration_seconds = (now - started).total_seconds()
        count += 1
    if count:
        await db.flush()
    return count


async def _cancel_scan(db: AsyncSession, scan: Scan, *, reason: str) -> None:
    if scan.celery_task_id:
        _revoke_celery(scan.celery_task_id)
    now = utcnow()
    scan.cancel_requested = True
    scan.status = ScanStatus.CANCELLED.value
    scan.completed_at = now
    scan.current_stage = "cancelled"
    scan.error_message = reason
    scan.stage_timings = close_stage_timings(scan.stage_timings, now=now)
    started = as_aware(scan.started_at)
    if started and scan.duration_seconds is None:
        scan.duration_seconds = (now - started).total_seconds()
    await db.flush()


def _revoke_celery(task_id: str) -> None:
    try:
        from app.core.celery_app import celery_app

        celery_app.control.revoke(task_id, terminate=True)
    except Exception:  # noqa: BLE001
        logger.debug("celery_revoke_failed", task_id=task_id)


async def archive_repository(
    db: AsyncSession,
    repo: Repository,
    *,
    actor: Optional[User],
    plan: str,
    reason: Optional[str] = None,
) -> Repository:
    now = utcnow()
    cancelled = await cancel_active_scans(
        db, repo.id, reason="Cancelled — repository archived"
    )
    await cancel_active_simulations(
        db, repo.id, reason="Cancelled — repository archived"
    )
    repo.is_archived = True
    repo.archived_at = now
    repo.is_watching = False
    repo.sync_status = RepositorySyncStatus.IDLE.value
    details: dict = {"cancelled_scans": cancelled}
    if reason:
        details["reason"] = reason
    await record_audit_event(
        db,
        organization_id=repo.organization_id,
        plan=plan,
        actor_user_id=actor.id if actor else None,
        action="repository.archived",
        resource_type="repository",
        resource_id=str(repo.id),
        resource_name=repo.full_name,
        details=details,
    )
    await db.flush()
    return repo


async def unarchive_repository(
    db: AsyncSession,
    repo: Repository,
    *,
    actor: User,
    plan: str,
) -> Repository:
    repo.is_archived = False
    repo.archived_at = None
    await record_audit_event(
        db,
        organization_id=repo.organization_id,
        plan=plan,
        actor_user_id=actor.id,
        action="repository.unarchived",
        resource_type="repository",
        resource_id=str(repo.id),
        resource_name=repo.full_name,
    )
    await db.flush()
    return repo


async def pause_sync(
    db: AsyncSession,
    repo: Repository,
    *,
    actor: User,
    plan: str,
) -> Repository:
    if repo.is_archived:
        raise ValueError("Archived repositories are already paused — unarchive to manage sync")
    repo.is_watching = False
    await record_audit_event(
        db,
        organization_id=repo.organization_id,
        plan=plan,
        actor_user_id=actor.id,
        action="repository.sync_paused",
        resource_type="repository",
        resource_id=str(repo.id),
        resource_name=repo.full_name,
    )
    await db.flush()
    return repo


async def resume_sync(
    db: AsyncSession,
    repo: Repository,
    *,
    actor: User,
    plan: str,
) -> Repository:
    if repo.is_archived:
        raise ValueError("Unarchive the repository before resuming sync")
    repo.is_watching = True
    await record_audit_event(
        db,
        organization_id=repo.organization_id,
        plan=plan,
        actor_user_id=actor.id,
        action="repository.sync_resumed",
        resource_type="repository",
        resource_id=str(repo.id),
        resource_name=repo.full_name,
    )
    await db.flush()
    return repo


async def remove_repository(
    db: AsyncSession,
    repo: Repository,
    *,
    actor: User,
    plan: str,
    delete_github_webhook: Optional[Callable[[Repository], Awaitable[None]]] = None,
) -> dict:
    """
    Permanently remove Verspect data for a repository.

    Never deletes the GitHub repository. Cancels jobs, writes audit log (Team+),
    hard-deletes the row (DB cascades clean related records), then removes the
    local clone cache outside the DB transaction.
    """
    repo_id = repo.id
    full_name = repo.full_name
    org_id = repo.organization_id
    local_hint = repo.local_path

    cancelled_scans = await cancel_active_scans(
        db, repo_id, reason="Cancelled — repository removed from Verspect"
    )
    cancelled_sims = await cancel_active_simulations(
        db, repo_id, reason="Cancelled — repository removed from Verspect"
    )

    webhook_removed = False
    if delete_github_webhook and repo.webhook_id and repo.webhook_active:
        try:
            await delete_github_webhook(repo)
            webhook_removed = True
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "webhook_delete_failed_on_remove",
                repository_id=str(repo_id),
                error=str(exc),
            )

    await record_audit_event(
        db,
        organization_id=org_id,
        plan=plan,
        actor_user_id=actor.id,
        action="repository.removed",
        resource_type="repository",
        resource_id=str(repo_id),
        resource_name=full_name,
        details={
            "cancelled_scans": cancelled_scans,
            "cancelled_simulations": cancelled_sims,
            "webhook_removed": webhook_removed,
            "github_repository_preserved": True,
        },
    )

    # Hard delete — FK cascades remove dependencies, scans, alerts, usages,
    # simulations, migration reports, etc. Feature usage events SET NULL.
    await db.delete(repo)
    await db.flush()

    logger.info(
        "repository_removed",
        repository_id=str(repo_id),
        full_name=full_name,
        cancelled_scans=cancelled_scans,
    )
    return {
        "repository_id": str(repo_id),
        "full_name": full_name,
        "cancelled_scans": cancelled_scans,
        "cancelled_simulations": cancelled_sims,
        "github_repository_preserved": True,
        "cleanup_clone_id": str(repo_id),
        "local_path_hint": local_hint,
    }
