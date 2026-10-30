"""Automatic Repository Scan recovery after unexpected worker death.

Reclaims the *same* Scan row (never inserts a duplicate), revokes the dead
Celery task, and re-enqueues exactly once per recovery attempt under a CAS
ownership guard.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import RepositorySyncStatus, ScanStatus, ScanType
from app.core.logging import get_logger
from app.models.repository import Repository
from app.models.scan import Scan
from app.services.job_health import close_stage_timings, record_stage_timing, utcnow

logger = get_logger(__name__)

RECOVERING_STAGE = "recovering"
RECOVERING_MESSAGE = "Recovering scan..."
RECOVERY_META_KEY = "recovery"

RecoveryResult = Literal["recovered", "skipped", "exhausted", "enqueue_failed"]

# Statuses that indicate a live worker still owns the scan (heartbeat-based reclaim).
_RUNNING_OWNED_STATUSES = {
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

_TERMINAL = {
    ScanStatus.COMPLETED.value,
    ScanStatus.FAILED.value,
    ScanStatus.CANCELLED.value,
}


def is_repository_scan(scan: Scan) -> bool:
    return (scan.scan_type or "") != ScanType.AI_ADVISOR.value


def recovery_metadata(scan: Scan) -> dict[str, Any]:
    meta = dict(scan.extra_metadata or {})
    raw = meta.get(RECOVERY_META_KEY) or {}
    return dict(raw) if isinstance(raw, dict) else {}


def recovery_count(scan: Scan) -> int:
    try:
        return int(recovery_metadata(scan).get("recovery_count") or 0)
    except (TypeError, ValueError):
        return 0


def is_recovering(scan: Scan) -> bool:
    """True while the scan is queued after an automatic reclaim."""
    if (scan.current_stage or "") == RECOVERING_STAGE:
        return True
    if (scan.error_message or "") == RECOVERING_MESSAGE:
        return True
    meta = recovery_metadata(scan)
    return bool(meta.get("recovered_from_worker_failure")) and (
        (scan.status or "") in {ScanStatus.QUEUED.value, ScanStatus.PENDING.value}
    )


def max_recoveries() -> int:
    settings = get_settings()
    return max(1, int(getattr(settings, "job_max_auto_retries", 2) or 2))


def _revoke(task_id: Optional[str]) -> None:
    if not task_id:
        return
    try:
        from app.core.celery_app import celery_app

        celery_app.control.revoke(task_id, terminate=True)
    except Exception:  # noqa: BLE001
        logger.debug("scan_recovery_revoke_failed", task_id=task_id)


def _build_recovery_blob(
    scan: Scan,
    *,
    original_task_id: Optional[str],
    now: datetime,
    from_worker: Optional[str],
) -> dict[str, Any]:
    prior = recovery_metadata(scan)
    count = int(prior.get("recovery_count") or 0) + 1
    history = list(prior.get("history") or [])
    history.append(
        {
            "recovered_at": now.isoformat(),
            "original_task_id": original_task_id,
            "from_worker": from_worker,
            "stage_before": scan.current_stage,
            "status_before": scan.status,
        }
    )
    # Bound history so JSONB does not grow without limit across long-lived rows.
    history = history[-10:]
    return {
        "recovery_count": count,
        "recovered_from_worker_failure": True,
        "recovered_at": now.isoformat(),
        "original_task_id": original_task_id,
        "new_task_id": None,
        "from_worker": from_worker,
        "history": history,
    }


def try_recover_abandoned_repository_scan(
    session: Session,
    scan: Scan,
    *,
    now: Optional[datetime] = None,
) -> RecoveryResult:
    """
    Atomically reclaim an abandoned Repository Scan and re-enqueue it.

    Idempotent: a second caller loses the CAS and returns ``skipped``.
    Never inserts a new Scan row. Does not touch AI advisor scans.
    """
    now = now or utcnow()
    session.refresh(scan)

    if not is_repository_scan(scan):
        return "skipped"
    if scan.cancel_requested or (scan.status or "") in _TERMINAL:
        return "skipped"
    if (scan.status or "") not in _RUNNING_OWNED_STATUSES:
        # Already queued/pending (possibly recovering) — do not create a second task.
        return "skipped"
    if recovery_count(scan) >= max_recoveries():
        return "exhausted"

    original_task_id = scan.celery_task_id
    from_worker = scan.worker_name
    recovery_blob = _build_recovery_blob(
        scan,
        original_task_id=original_task_id,
        now=now,
        from_worker=from_worker,
    )
    extra = dict(scan.extra_metadata or {})
    extra[RECOVERY_META_KEY] = recovery_blob

    # Preserve prior stage trail then open a recovering stage for observability.
    timings = close_stage_timings(scan.stage_timings, now=now)
    timings = record_stage_timing(timings, RECOVERING_STAGE, now=now)

    # CAS: only the owner of the abandoned running row may reclaim it.
    # Matching celery_task_id (or NULL) prevents two reclaimers from both winning.
    values = {
        "status": ScanStatus.QUEUED.value,
        "progress_percent": 0,
        # Keep stage=recovering until a worker claims the row (UI: "Recovering scan...").
        "current_stage": RECOVERING_STAGE,
        "error_message": RECOVERING_MESSAGE,
        "error_traceback": None,
        "started_at": None,
        "completed_at": None,
        "duration_seconds": None,
        "queued_at": now,
        "last_heartbeat_at": None,
        "worker_name": None,
        "celery_task_id": None,
        "cancel_requested": False,
        "retry_count": int(scan.retry_count or 0) + 1,
        "stage_timings": timings,
        "extra_metadata": extra,
    }

    where = [
        Scan.id == scan.id,
        Scan.cancel_requested.is_(False),
        Scan.status.in_(tuple(_RUNNING_OWNED_STATUSES)),
        Scan.status.notin_(tuple(_TERMINAL)),
    ]
    if original_task_id:
        where.append(Scan.celery_task_id == original_task_id)
    else:
        where.append(Scan.celery_task_id.is_(None))

    result = session.execute(update(Scan).where(*where).values(**values))
    if int(result.rowcount or 0) != 1:
        session.rollback()
        logger.info(
            "scan_recovery_cas_lost",
            scan_id=str(scan.id),
            original_task_id=original_task_id,
        )
        return "skipped"

    session.commit()
    session.refresh(scan)

    # Dead task must not continue writing after we cleared ownership.
    _revoke(original_task_id)

    repo = session.get(Repository, scan.repository_id)
    if repo is not None:
        repo.sync_status = RepositorySyncStatus.SYNCING.value

    try:
        from app.services.tasks.scan_tasks import run_repository_scan

        task = run_repository_scan.delay(str(scan.id))
        new_task_id = task.id
    except Exception as exc:  # noqa: BLE001
        scan.status = ScanStatus.FAILED.value
        scan.current_stage = "failed"
        scan.error_message = (
            "Automatic recovery could not re-queue this scan. Please retry."
        )
        scan.error_traceback = str(exc)[:8000]
        scan.completed_at = now
        scan.stage_timings = close_stage_timings(scan.stage_timings, now=now)
        if repo is not None:
            from app.services.repository_counters import sync_repository_counters

            repo.sync_status = RepositorySyncStatus.ERROR.value
            sync_repository_counters(session, repo)
        session.commit()
        logger.error(
            "scan_recovery_enqueue_failed",
            scan_id=str(scan.id),
            error=str(exc),
        )
        return "enqueue_failed"

    # Persist new task id under the same recovery blob (single writer after CAS).
    meta = dict(scan.extra_metadata or {})
    blob = dict(meta.get(RECOVERY_META_KEY) or {})
    blob["new_task_id"] = new_task_id
    meta[RECOVERY_META_KEY] = blob
    # Second CAS: only attach task id if we still own the recovering row.
    attached = session.execute(
        update(Scan)
        .where(
            Scan.id == scan.id,
            Scan.cancel_requested.is_(False),
            Scan.status == ScanStatus.QUEUED.value,
            Scan.current_stage == RECOVERING_STAGE,
            Scan.celery_task_id.is_(None),
        )
        .values(celery_task_id=new_task_id, extra_metadata=meta)
    )
    if int(attached.rowcount or 0) != 1:
        _revoke(new_task_id)
        session.rollback()
        logger.warning(
            "scan_recovery_attach_lost",
            scan_id=str(scan.id),
            new_task_id=new_task_id,
        )
        return "skipped"

    session.commit()
    session.refresh(scan)
    logger.info(
        "scan_recovered_from_worker_failure",
        scan_id=str(scan.id),
        recovery_count=blob.get("recovery_count"),
        original_task_id=original_task_id,
        new_task_id=new_task_id,
        from_worker=from_worker,
    )
    return "recovered"


def fail_recovery_exhausted(session: Session, scan: Scan, *, now: Optional[datetime] = None) -> None:
    """Mark a scan failed after recovery budget is spent."""
    now = now or utcnow()
    scan.status = ScanStatus.FAILED.value
    scan.current_stage = "failed"
    scan.error_message = (
        "Automatic recovery could not complete this scan after repeated "
        "worker failures. Please retry."
    )
    scan.completed_at = now
    scan.stage_timings = close_stage_timings(scan.stage_timings, now=now)
    if is_repository_scan(scan):
        repo = session.get(Repository, scan.repository_id)
        if repo is not None:
            from app.services.repository_counters import sync_repository_counters

            repo.sync_status = RepositorySyncStatus.ERROR.value
            sync_repository_counters(session, repo)
    _revoke(scan.celery_task_id)
    session.commit()


def parent_already_has_ai_advisor(session: Session, parent_scan_id: UUID) -> Optional[Scan]:
    """Return an existing AI advisor job linked to this parent scan, if any."""
    parent = session.get(Scan, parent_scan_id)
    if parent is None:
        return None
    existing_id = dict(parent.summary or {}).get("ai_advisor_scan_id")
    if not existing_id:
        return None
    try:
        return session.get(Scan, UUID(str(existing_id)))
    except (ValueError, TypeError):
        return None
