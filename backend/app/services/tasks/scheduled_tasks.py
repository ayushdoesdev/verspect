"""Celery beat scheduled tasks."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.database import SyncSessionLocal
from app.core.enums import ScanStatus, ScanType
from app.core.logging import get_logger
from app.models.repository import Repository
from app.models.scan import Scan
from app.services.clone import cleanup_repository

logger = get_logger(__name__)
settings = get_settings()


def _org_allows_scheduled_scans(session, repo: Repository) -> bool:
    """Scheduled scans require active Pro+ entitlements (not evaluation)."""
    from app.models.billing import Subscription
    from app.models.organization import Organization
    from app.services.entitlements import resolve_entitlements

    if not repo.organization_id:
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
    return bool(ents.scheduled_scans and ents.can_run_background_jobs)


@celery_app.task(name="app.services.tasks.scheduled_tasks.daily_rescan_all")
def daily_rescan_all() -> dict[str, Any]:
    session = SyncSessionLocal()
    try:
        repos = (
            session.execute(
                select(Repository).where(
                    Repository.is_watching.is_(True),
                    Repository.deleted_at.is_(None),
                    Repository.is_archived.is_(False),
                )
            )
            .scalars()
            .all()
        )
        from app.services.tasks.scan_tasks import run_repository_scan

        queued = []
        skipped = 0
        for repo in repos:
            if not _org_allows_scheduled_scans(session, repo):
                skipped += 1
                continue
            scan = Scan(
                repository_id=repo.id,
                triggered_by_user_id=repo.owner_id,
                scan_type=ScanType.SCHEDULED.value,
                branch=repo.default_branch,
                previous_commit_sha=repo.last_commit_sha,
                status=ScanStatus.QUEUED.value,
            )
            session.add(scan)
            session.flush()
            session.commit()
            task = run_repository_scan.delay(str(scan.id))
            scan.celery_task_id = task.id
            session.commit()
            queued.append(str(scan.id))
        logger.info("daily_rescan_queued", count=len(queued), skipped=skipped)
        return {"queued": len(queued), "scan_ids": queued, "skipped": skipped}
    finally:
        session.close()


@celery_app.task(name="app.services.tasks.scheduled_tasks.hourly_version_check")
def hourly_version_check() -> dict[str, Any]:
    """Lightweight check: queue incremental scans for watching repos."""
    session = SyncSessionLocal()
    try:
        repos = (
            session.execute(
                select(Repository).where(
                    Repository.is_watching.is_(True),
                    Repository.deleted_at.is_(None),
                    Repository.is_archived.is_(False),
                )
            )
            .scalars()
            .all()
        )
        from app.services.tasks.scan_tasks import run_repository_scan

        queued = 0
        for repo in repos:
            if not _org_allows_scheduled_scans(session, repo):
                continue
            # Skip if a scan is already running
            active = session.execute(
                select(Scan).where(
                    Scan.repository_id == repo.id,
                    Scan.status.in_(
                        [
                            ScanStatus.QUEUED.value,
                            ScanStatus.CLONING.value,
                            ScanStatus.SCANNING_MANIFESTS.value,
                            ScanStatus.PARSING_AST.value,
                            ScanStatus.CHECKING_VERSIONS.value,
                        ]
                    ),
                )
            ).scalars().first()
            if active:
                continue
            scan = Scan(
                repository_id=repo.id,
                triggered_by_user_id=repo.owner_id,
                scan_type=ScanType.INCREMENTAL.value,
                branch=repo.default_branch,
                previous_commit_sha=repo.last_commit_sha,
                status=ScanStatus.QUEUED.value,
            )
            session.add(scan)
            session.flush()
            session.commit()
            task = run_repository_scan.delay(str(scan.id))
            scan.celery_task_id = task.id
            session.commit()
            queued += 1
        return {"queued": queued}
    finally:
        session.close()


@celery_app.task(name="app.services.tasks.scheduled_tasks.cleanup_stale_clones")
def cleanup_stale_clones(max_age_hours: int = 72) -> dict[str, Any]:
    base = Path(settings.scan_clone_dir)
    if not base.exists():
        return {"removed": 0}
    removed = 0
    cutoff = time.time() - max_age_hours * 3600
    session = SyncSessionLocal()
    try:
        watched_ids = {
            str(r.id)
            for r in session.execute(
                select(Repository.id).where(
                    Repository.is_watching.is_(True),
                    Repository.deleted_at.is_(None),
                    Repository.is_archived.is_(False),
                )
            ).scalars().all()
        }
        for child in base.iterdir():
            if not child.is_dir():
                continue
            # Remove if not watching or stale mtime
            mtime = child.stat().st_mtime
            if child.name not in watched_ids or mtime < cutoff:
                cleanup_repository(child.name)
                removed += 1
        return {"removed": removed}
    finally:
        session.close()


@celery_app.task(name="app.services.tasks.scheduled_tasks.cleanup_stale_scans")
def cleanup_stale_scans() -> dict[str, Any]:
    """
    Reap background jobs that can no longer make progress.

    Catches three classes of failure for both scans and upgrade simulations:
      * never picked up (broker/worker down)
      * worker died mid-run (heartbeat went silent)
      * exceeded the configured maximum runtime

    This is the safety net for jobs nobody is polling — the API reconciles the
    ones a user is actively watching.
    """
    from app.api.v1.dependencies import (
        ACTIVE_SIMULATION_STATUSES,
        PENDING_SIMULATION_STATUSES,
        TERMINAL_SIMULATION_STATUSES,
    )
    from app.api.v1.scans import (
        ACTIVE_SCAN_STATUSES,
        PENDING_SCAN_STATUSES,
        TERMINAL_SCAN_STATUSES,
    )
    from app.core.config import get_settings
    from app.core.enums import RepositorySyncStatus, SimulationStatus
    from app.models.upgrade_simulation import UpgradeSimulation
    from app.services.job_health import (
        as_aware,
        classify_job,
        close_stage_timings,
        get_worker_health,
        utcnow,
    )

    settings = get_settings()
    # Only liveness matters here, so skip the expensive active/reserved probes.
    worker_online = get_worker_health(detailed=False).online
    session = SyncSessionLocal()
    reaped_scans = 0
    reaped_simulations = 0

    try:
        now = utcnow()

        scans = (
            session.execute(select(Scan).where(Scan.status.in_(ACTIVE_SCAN_STATUSES)))
            .scalars()
            .all()
        )
        for scan in scans:
            from app.core.enums import ScanType

            is_ai_advisor = (scan.scan_type or "") == ScanType.AI_ADVISOR.value
            verdict = classify_job(
                status=scan.status,
                terminal_statuses=TERMINAL_SCAN_STATUSES,
                pending_statuses=PENDING_SCAN_STATUSES,
                queued_at=scan.queued_at or scan.created_at,
                started_at=scan.started_at,
                last_heartbeat_at=scan.last_heartbeat_at,
                pickup_timeout_seconds=settings.scan_pickup_timeout_seconds,
                running_timeout_minutes=settings.scan_running_timeout_minutes,
                worker_online=worker_online,
                now=now,
            )
            if not verdict.is_unhealthy:
                continue

            # Silent one-shot retry for Repository Scan pickup timeouts (import UX).
            if (
                verdict.state == "pickup_timeout"
                and not is_ai_advisor
                and (scan.retry_count or 0) == 0
            ):
                previous = scan.celery_task_id
                _revoke(previous)
                scan.status = ScanStatus.QUEUED.value
                scan.progress_percent = 0
                scan.current_stage = "queued"
                scan.error_message = None
                scan.error_traceback = None
                scan.started_at = None
                scan.completed_at = None
                scan.queued_at = now
                scan.last_heartbeat_at = None
                scan.worker_name = None
                scan.celery_task_id = None
                scan.cancel_requested = False
                scan.retry_count = 1
                scan.stage_timings = []
                repo = session.get(Repository, scan.repository_id)
                if repo:
                    repo.sync_status = RepositorySyncStatus.SYNCING.value
                try:
                    from app.services.tasks.scan_tasks import run_repository_scan

                    task = run_repository_scan.delay(str(scan.id))
                    scan.celery_task_id = task.id
                    logger.info(
                        "scan_auto_retried_by_scheduler",
                        scan_id=str(scan.id),
                    )
                except Exception as exc:  # noqa: BLE001
                    scan.status = ScanStatus.FAILED.value
                    scan.error_message = str(exc)[:2000]
                    scan.current_stage = "failed"
                    scan.completed_at = now
                    if repo:
                        repo.sync_status = RepositorySyncStatus.ERROR.value
                continue

            # Worker died mid-run: reclaim the same Scan row (never insert a duplicate).
            if verdict.state == "heartbeat_lost" and not is_ai_advisor:
                from app.services.scan_recovery import (
                    fail_recovery_exhausted,
                    try_recover_abandoned_repository_scan,
                )

                outcome = try_recover_abandoned_repository_scan(
                    session, scan, now=now
                )
                if outcome == "recovered":
                    logger.info(
                        "scan_auto_recovered_by_scheduler",
                        scan_id=str(scan.id),
                    )
                    continue
                if outcome == "exhausted":
                    fail_recovery_exhausted(session, scan, now=now)
                    reaped_scans += 1
                    continue
                if outcome == "enqueue_failed":
                    reaped_scans += 1
                    continue
                # CAS lost — another reclaim already owns this row.
                continue

            scan.status = ScanStatus.FAILED.value
            scan.error_message = verdict.message or "Scan did not complete."
            scan.completed_at = now
            scan.current_stage = "failed"
            scan.stage_timings = close_stage_timings(scan.stage_timings, now=now)
            started = as_aware(scan.started_at)
            if started and scan.duration_seconds is None:
                scan.duration_seconds = (now - started).total_seconds()
            if not is_ai_advisor:
                from app.services.repository_counters import sync_repository_counters

                repo = session.get(Repository, scan.repository_id)
                if repo:
                    repo.sync_status = RepositorySyncStatus.ERROR.value
                    sync_repository_counters(session, repo)
            _revoke(scan.celery_task_id)
            reaped_scans += 1
            logger.warning(
                "scan_reaped_by_scheduler",
                scan_id=str(scan.id),
                state=verdict.state,
                worker=scan.worker_name,
                retry_count=scan.retry_count,
                scan_type=scan.scan_type,
            )

        simulations = (
            session.execute(
                select(UpgradeSimulation).where(
                    UpgradeSimulation.status.in_(ACTIVE_SIMULATION_STATUSES)
                )
            )
            .scalars()
            .all()
        )
        for sim in simulations:
            verdict = classify_job(
                status=sim.status,
                terminal_statuses=TERMINAL_SIMULATION_STATUSES,
                pending_statuses=PENDING_SIMULATION_STATUSES,
                queued_at=sim.queued_at or sim.created_at,
                started_at=sim.started_at,
                last_heartbeat_at=sim.last_heartbeat_at,
                pickup_timeout_seconds=settings.simulation_pickup_timeout_seconds,
                running_timeout_minutes=settings.simulation_running_timeout_minutes,
                worker_online=worker_online,
                now=now,
            )
            if not verdict.is_unhealthy:
                continue

            sim.status = SimulationStatus.FAILED.value
            sim.error_message = verdict.message or "Simulation did not complete."
            sim.completed_at = now
            sim.current_stage = "failed"
            sim.stage_timings = close_stage_timings(sim.stage_timings, now=now)
            started = as_aware(sim.started_at)
            if started and sim.duration_seconds is None:
                sim.duration_seconds = (now - started).total_seconds()
            _revoke(sim.celery_task_id)
            reaped_simulations += 1
            logger.warning(
                "simulation_reaped_by_scheduler",
                simulation_id=str(sim.id),
                state=verdict.state,
                worker=sim.worker_name,
            )

        session.commit()
        if reaped_scans or reaped_simulations:
            logger.info(
                "stale_jobs_reaped",
                scans=reaped_scans,
                simulations=reaped_simulations,
                worker_online=worker_online,
            )
        return {
            "cleaned": reaped_scans,
            "scans": reaped_scans,
            "simulations": reaped_simulations,
            "worker_online": worker_online,
        }
    finally:
        session.close()


def _revoke(task_id: Optional[str]) -> None:
    if not task_id:
        return
    try:
        celery_app.control.revoke(task_id, terminate=True)
    except Exception:  # noqa: BLE001
        logger.debug("revoke_failed", task_id=task_id)


@celery_app.task(name="app.services.tasks.scheduled_tasks.apply_subscription_lifecycle")
def apply_subscription_lifecycle() -> dict[str, Any]:
    """Apply due plan downgrades and cancel→Evaluation transitions (data-safe)."""
    import asyncio

    from app.core.database import AsyncSessionLocal
    from app.services.billing.lifecycle import apply_due_for_all_orgs

    async def _run() -> int:
        async with AsyncSessionLocal() as db:
            count = await apply_due_for_all_orgs(db)
            await db.commit()
            return count

    applied = asyncio.run(_run())
    if applied:
        logger.info("subscription_lifecycle_applied", count=applied)
    return {"applied": applied}

