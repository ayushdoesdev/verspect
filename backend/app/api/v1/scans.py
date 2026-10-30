"""Scan management endpoints — lifecycle, health, retry and cancellation."""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps.auth import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.enums import RepositorySyncStatus, ScanStatus, ScanType
from app.core.logging import get_logger
from app.core.pagination import PaginatedResponse
from app.models.repository import Repository
from app.models.scan import Scan
from app.schemas.alert import ScanCreateRequest, ScanResponse
from app.services.job_health import (
    as_aware,
    classify_job,
    close_stage_timings,
    get_worker_health,
    utcnow,
)
from app.services.organizations import get_active_organization

router = APIRouter()
logger = get_logger(__name__)

PENDING_SCAN_STATUSES = {ScanStatus.PENDING.value, ScanStatus.QUEUED.value}

RUNNING_SCAN_STATUSES = {
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

TERMINAL_SCAN_STATUSES = {
    ScanStatus.COMPLETED.value,
    ScanStatus.FAILED.value,
    ScanStatus.CANCELLED.value,
}

ACTIVE_SCAN_STATUSES = PENDING_SCAN_STATUSES | RUNNING_SCAN_STATUSES


async def _load_scan(db: DbSession, current_user: CurrentUser, scan_id: UUID) -> Scan:
    org = await get_active_organization(db, current_user)
    result = await db.execute(
        select(Scan)
        .join(Repository, Scan.repository_id == Repository.id)
        .where(
            Scan.id == scan_id,
            Repository.organization_id == org.id,
            Repository.deleted_at.is_(None),
        )
    )
    scan = result.scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return scan


def _is_ai_advisor_scan(scan: Scan) -> bool:
    return (scan.scan_type or "") == ScanType.AI_ADVISOR.value


async def _fail_unhealthy_scan(db: DbSession, scan: Scan, message: str) -> None:
    now = utcnow()
    scan.status = ScanStatus.FAILED.value
    scan.error_message = message
    scan.completed_at = now
    scan.current_stage = "failed"
    scan.stage_timings = close_stage_timings(scan.stage_timings, now=now)
    started = as_aware(scan.started_at)
    if started and scan.duration_seconds is None:
        scan.duration_seconds = (now - started).total_seconds()

    # AI Upgrade Advisor must never flip repository sync to error.
    if not _is_ai_advisor_scan(scan):
        from app.services.repository_counters import async_sync_repository_counters

        repo = (
            await db.execute(select(Repository).where(Repository.id == scan.repository_id))
        ).scalar_one_or_none()
        if repo:
            repo.sync_status = RepositorySyncStatus.ERROR.value
            await async_sync_repository_counters(db, repo)

    if scan.celery_task_id:
        try:
            from app.core.celery_app import celery_app

            celery_app.control.revoke(scan.celery_task_id, terminate=True)
        except Exception:  # noqa: BLE001
            pass

    await db.commit()
    await db.refresh(scan)
    logger.warning(
        "scan_reaped",
        scan_id=str(scan.id),
        reason=message,
        worker=scan.worker_name,
        retry_count=scan.retry_count,
        scan_type=scan.scan_type,
    )


async def _auto_retry_pickup_timeout(db: DbSession, scan: Scan) -> bool:
    """One silent retry when no worker picked up an import/scan. Returns True if retried."""
    if _is_ai_advisor_scan(scan):
        return False
    if (scan.retry_count or 0) > 0:
        return False
    if scan.status not in PENDING_SCAN_STATUSES:
        return False

    from app.services.celery_task_control import revoke_and_wait

    previous = scan.celery_task_id
    if previous:
        revoke_and_wait(previous, timeout_seconds=5.0)

    repo = (
        await db.execute(select(Repository).where(Repository.id == scan.repository_id))
    ).scalar_one_or_none()
    if repo is None:
        return False

    now = utcnow()
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
    repo.sync_status = RepositorySyncStatus.SYNCING.value
    await db.flush()
    await _dispatch_scan(db, scan, repo)
    await db.commit()
    await db.refresh(scan)
    logger.info(
        "scan_auto_retried_pickup_timeout",
        scan_id=str(scan.id),
        retry_count=scan.retry_count,
    )
    return True


async def _auto_recover_heartbeat_lost(db: DbSession, scan: Scan) -> bool:
    """
    Reclaim an abandoned Repository Scan on the sync session (CAS + re-enqueue).

    Returns True when the scan was recovered or already handled (exhausted /
    enqueue failure written). False when another reclaim won the CAS.
    """
    if _is_ai_advisor_scan(scan):
        return False

    import asyncio

    from app.core.database import SyncSessionLocal
    from app.services.scan_recovery import (
        fail_recovery_exhausted,
        try_recover_abandoned_repository_scan,
    )

    scan_id = scan.id

    def _run() -> str:
        session = SyncSessionLocal()
        try:
            row = session.get(Scan, scan_id)
            if row is None:
                return "skipped"
            outcome = try_recover_abandoned_repository_scan(session, row)
            if outcome == "exhausted":
                fail_recovery_exhausted(session, row)
            return outcome
        finally:
            session.close()

    outcome = await asyncio.to_thread(_run)
    await db.refresh(scan)
    if outcome == "recovered":
        logger.info("scan_auto_recovered_by_api", scan_id=str(scan.id))
        return True
    if outcome in {"exhausted", "enqueue_failed"}:
        return True
    return False


async def _reconcile_scan(db: DbSession, scan: Scan, *, worker_online: bool) -> Scan:
    """
    Apply lifecycle rules to a single scan.

    Turns silent "stuck in pending forever" states into explicit failures so the
    UI can offer retry instead of spinning indefinitely. Abandoned mid-run
    Repository Scans are reclaimed automatically instead of failing immediately.
    """
    settings = get_settings()
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
    )
    if verdict.state == "pickup_timeout":
        retried = await _auto_retry_pickup_timeout(db, scan)
        if retried:
            return scan
    if verdict.state == "heartbeat_lost" and not _is_ai_advisor_scan(scan):
        handled = await _auto_recover_heartbeat_lost(db, scan)
        if handled:
            return scan
    if verdict.is_unhealthy:
        await _fail_unhealthy_scan(db, scan, verdict.message or "Scan did not complete.")
    return scan


async def _queue_position(db: DbSession, scan: Scan) -> Optional[int]:
    """How many jobs are waiting ahead of this one (1-based)."""
    if scan.status not in PENDING_SCAN_STATUSES or scan.started_at is not None:
        return None
    reference = scan.queued_at or scan.created_at
    # Compare the same expression on both sides, and never count the scan
    # itself — `queued_at` and `created_at` differ by microseconds.
    queued_expr = func.coalesce(Scan.queued_at, Scan.created_at)
    ahead = await db.scalar(
        select(func.count())
        .select_from(Scan)
        .where(
            Scan.id != scan.id,
            Scan.status.in_(PENDING_SCAN_STATUSES),
            Scan.started_at.is_(None),
            queued_expr < reference,
        )
    )
    return int(ahead or 0) + 1


def _serialize(scan: Scan, *, queue_position: Optional[int] = None) -> ScanResponse:
    response = ScanResponse.model_validate(scan)
    response.queue_position = queue_position
    return response


@router.get("/worker-status")
async def get_worker_status() -> dict[str, Any]:
    """Worker + queue health used by the UI to explain delays instead of spinning."""
    return get_worker_health().to_dict()


@router.post(
    "/repositories/{repository_id}",
    response_model=ScanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_scan(
    repository_id: UUID,
    body: ScanCreateRequest,
    current_user: CurrentUser,
    db: DbSession,
    force: bool = Query(
        False,
        description="Cancel any in-flight scan for this repository and start a fresh one.",
    ),
) -> ScanResponse:
    from app.services.entitlements import count_scans_this_month, require_write_access
    from app.services.plans import assert_scan_limit

    org = await get_active_organization(db, current_user)
    result = await db.execute(
        select(Repository).where(
            Repository.id == repository_id,
            Repository.organization_id == org.id,
            Repository.deleted_at.is_(None),
        )
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if getattr(repo, "is_archived", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Archived repositories cannot be scanned. Unarchive the repository first.",
        )

    await require_write_access(db, org=org, feature="scans")
    scans_used = await count_scans_this_month(
        db, org=org, owner_user_id=current_user.id
    )
    assert_scan_limit(org.plan, scans_used)

    worker_health = get_worker_health()

    # Duplicate prevention: reuse the in-flight scan unless the caller explicitly
    # asks to replace it.
    active_result = await db.execute(
        select(Scan)
        .where(
            Scan.repository_id == repository_id,
            Scan.status.in_(ACTIVE_SCAN_STATUSES),
            Scan.scan_type != ScanType.AI_ADVISOR.value,
        )
        .order_by(Scan.created_at.desc())
    )
    existing_active = active_result.scalars().first()
    if existing_active:
        await _reconcile_scan(db, existing_active, worker_online=worker_health.online)
        if existing_active.status in ACTIVE_SCAN_STATUSES:
            if not force:
                return _serialize(
                    existing_active,
                    queue_position=await _queue_position(db, existing_active),
                )
            import asyncio

            from app.services.celery_task_control import revoke_and_wait

            previous_task_id = existing_active.celery_task_id
            await _cancel_scan_record(db, existing_active, reason="Superseded by a new scan")
            await db.commit()
            if previous_task_id:
                await asyncio.to_thread(
                    revoke_and_wait, previous_task_id, timeout_seconds=90.0
                )

    scan_type = (
        body.scan_type
        if body.scan_type in {t.value for t in ScanType} and body.scan_type != ScanType.AI_ADVISOR.value
        else ScanType.MANUAL.value
    )
    now = utcnow()
    scan = Scan(
        repository_id=repo.id,
        triggered_by_user_id=current_user.id,
        scan_type=scan_type,
        branch=repo.default_branch,
        previous_commit_sha=repo.last_commit_sha,
        status=ScanStatus.QUEUED.value,
        progress_percent=0,
        current_stage="queued",
        queued_at=now,
        stage_timings=[],
    )
    db.add(scan)
    repo.sync_status = RepositorySyncStatus.SYNCING.value
    await db.flush()
    # Persist the Scan row before Celery publish (acks_late workers race uncommitted rows).
    await db.commit()

    await _dispatch_scan(db, scan, repo)
    await db.commit()
    await db.refresh(scan)
    logger.info(
        "scan_enqueued",
        scan_id=str(scan.id),
        repository_id=str(repo.id),
        worker_online=worker_health.online,
    )
    return _serialize(scan, queue_position=await _queue_position(db, scan))


async def _dispatch_scan(db: DbSession, scan: Scan, repo: Repository) -> None:
    """Publish the Celery task after the Scan row is durable; record task id / failures."""
    try:
        if _is_ai_advisor_scan(scan):
            from app.services.tasks.ai_advisor_tasks import run_ai_upgrade_advisor

            task = run_ai_upgrade_advisor.delay(str(scan.id))
        else:
            from app.services.tasks.scan_tasks import run_repository_scan

            task = run_repository_scan.delay(str(scan.id))
        scan.celery_task_id = task.id
    except Exception as exc:  # noqa: BLE001
        scan.status = ScanStatus.FAILED.value
        scan.error_message = (
            "Background processing service is unavailable. Please try again shortly."
        )
        scan.error_traceback = str(exc)[:8000]
        scan.completed_at = utcnow()
        scan.current_stage = "failed"
        if not _is_ai_advisor_scan(scan):
            repo.sync_status = RepositorySyncStatus.ERROR.value
        logger.error("scan_dispatch_failed", scan_id=str(scan.id), error=str(exc))
    await db.flush()


async def _cancel_scan_record(db: DbSession, scan: Scan, *, reason: str) -> Scan:
    """Revoke the Celery task and mark the scan cancelled."""
    if scan.celery_task_id:
        try:
            from app.core.celery_app import celery_app

            celery_app.control.revoke(scan.celery_task_id, terminate=True)
        except Exception:  # noqa: BLE001
            logger.debug("scan_revoke_failed", scan_id=str(scan.id))

    now = utcnow()
    # Flag first so an already-running worker cancels at its next checkpoint.
    scan.cancel_requested = True
    scan.status = ScanStatus.CANCELLED.value
    scan.completed_at = now
    scan.current_stage = "cancelled"
    scan.error_message = reason
    scan.stage_timings = close_stage_timings(scan.stage_timings, now=now)
    started = as_aware(scan.started_at)
    if started and scan.duration_seconds is None:
        scan.duration_seconds = (now - started).total_seconds()

    repo = (
        await db.execute(select(Repository).where(Repository.id == scan.repository_id))
    ).scalar_one_or_none()
    if repo and not _is_ai_advisor_scan(scan):
        from app.services.repository_counters import async_sync_repository_counters

        repo.sync_status = RepositorySyncStatus.IDLE.value
        # Cancel often lands after deps are persisted but before completion aggregation.
        await async_sync_repository_counters(db, repo)
    elif repo:
        repo.sync_status = RepositorySyncStatus.IDLE.value

    await db.flush()
    logger.info("scan_cancelled", scan_id=str(scan.id), reason=reason)
    return scan


@router.get("", response_model=PaginatedResponse[ScanResponse])
async def list_scans(
    current_user: CurrentUser,
    db: DbSession,
    repository_id: UUID | None = None,
    active_only: bool = Query(False, description="Only pending/queued/running scans"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> PaginatedResponse[ScanResponse]:
    org = await get_active_organization(db, current_user)
    base = [
        Repository.deleted_at.is_(None),
        Repository.organization_id == org.id,
    ]
    query = select(Scan).join(Repository, Scan.repository_id == Repository.id).where(*base)
    count_query = (
        select(func.count())
        .select_from(Scan)
        .join(Repository, Scan.repository_id == Repository.id)
        .where(*base)
    )
    if repository_id:
        query = query.where(Scan.repository_id == repository_id)
        count_query = count_query.where(Scan.repository_id == repository_id)
    if active_only:
        query = query.where(Scan.status.in_(ACTIVE_SCAN_STATUSES))
        count_query = count_query.where(Scan.status.in_(ACTIVE_SCAN_STATUSES))

    query = query.order_by(Scan.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    total = (await db.execute(count_query)).scalar_one()
    rows = (await db.execute(query)).scalars().all()

    needs_health = any(r.status in ACTIVE_SCAN_STATUSES for r in rows)
    worker_online = get_worker_health().online if needs_health else True

    items: list[ScanResponse] = []
    for row in rows:
        if row.status in ACTIVE_SCAN_STATUSES:
            await _reconcile_scan(db, row, worker_online=worker_online)
        items.append(_serialize(row, queue_position=await _queue_position(db, row)))

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ScanResponse:
    scan = await _load_scan(db, current_user, scan_id)
    if scan.status in ACTIVE_SCAN_STATUSES:
        await _reconcile_scan(db, scan, worker_online=get_worker_health().online)
    return _serialize(scan, queue_position=await _queue_position(db, scan))


@router.post("/{scan_id}/cancel", response_model=ScanResponse)
async def cancel_scan(
    scan_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ScanResponse:
    scan = await _load_scan(db, current_user, scan_id)
    if scan.status in TERMINAL_SCAN_STATUSES:
        return _serialize(scan)

    await _cancel_scan_record(db, scan, reason="Scan cancelled by user")
    await db.commit()
    await db.refresh(scan)
    return _serialize(scan)


@router.post("/{scan_id}/retry", response_model=ScanResponse)
async def retry_scan(
    scan_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ScanResponse:
    """Cancel whatever is in flight and start a clean run from stage one."""
    import asyncio

    from app.services.celery_task_control import revoke_and_wait
    from app.services.entitlements import count_scans_this_month, require_write_access
    from app.services.plans import assert_scan_limit

    scan = await _load_scan(db, current_user, scan_id)

    repo = (
        await db.execute(select(Repository).where(Repository.id == scan.repository_id))
    ).scalar_one_or_none()
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found"
        )

    org = await get_active_organization(db, current_user)
    await require_write_access(db, org=org, feature="scans")
    scans_used = await count_scans_this_month(
        db, org=org, owner_user_id=current_user.id
    )
    assert_scan_limit(org.plan, scans_used)

    previous_task_id = scan.celery_task_id
    # Signal cooperative cancel first so the worker aborts between AI calls.
    if scan.status in ACTIVE_SCAN_STATUSES:
        scan.cancel_requested = True
        await db.flush()
        await db.commit()

    if previous_task_id:
        stopped = await asyncio.to_thread(
            revoke_and_wait, previous_task_id, timeout_seconds=90.0
        )
        if not stopped:
            logger.warning(
                "scan_retry_previous_still_active",
                scan_id=str(scan.id),
                previous_task_id=previous_task_id,
            )

    # Reload after waiting — worker may have written terminal state.
    await db.refresh(scan)
    await db.refresh(repo)

    now = utcnow()
    scan.status = ScanStatus.QUEUED.value
    scan.progress_percent = 0
    scan.current_stage = "queued"
    scan.error_message = None
    scan.error_traceback = None
    scan.started_at = None
    scan.completed_at = None
    scan.duration_seconds = None
    scan.queued_at = now
    scan.last_heartbeat_at = None
    scan.worker_name = None
    scan.celery_task_id = None
    scan.cancel_requested = False
    scan.retry_count = (scan.retry_count or 0) + 1
    scan.stage_timings = []
    if not _is_ai_advisor_scan(scan):
        repo.sync_status = RepositorySyncStatus.SYNCING.value
    await db.flush()

    await _dispatch_scan(db, scan, repo)
    await db.commit()
    await db.refresh(scan)
    logger.info("scan_retried", scan_id=str(scan.id), retry_count=scan.retry_count)
    return _serialize(scan, queue_position=await _queue_position(db, scan))
