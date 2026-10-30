"""Celery tasks — AI Upgrade Advisor (independent of Repository Scan)."""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select

from app.ai.analyzer import AIAnalyzer
from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.database import SyncSessionLocal
from app.core.enums import ScanStatus, ScanType
from app.core.logging import get_logger
from app.models.repository import Repository
from app.models.scan import Scan
from app.services.ai_upgrade_advisor import (
    org_supports_ai_advisor,
    run_ai_upgrade_advisor_for_repository,
)
from app.services.job_health import close_stage_timings, record_stage_timing

logger = get_logger(__name__)
_settings = get_settings()

_TERMINAL = {
    ScanStatus.COMPLETED.value,
    ScanStatus.FAILED.value,
    ScanStatus.CANCELLED.value,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_ai_upgrade_advisor(
    session,
    *,
    repository_id: UUID,
    parent_scan_id: Optional[UUID] = None,
    triggered_by_user_id: Optional[UUID] = None,
) -> Optional[Scan]:
    """Create an AI advisor Scan row and dispatch the analysis-queue worker.

    Returns None when the plan does not include AI Upgrade Advisor.
    """
    if not org_supports_ai_advisor(session, repository_id):
        logger.info(
            "ai_advisor_skipped_plan",
            repository_id=str(repository_id),
            parent_scan_id=str(parent_scan_id) if parent_scan_id else None,
        )
        return None

    active = (
        session.execute(
            select(Scan).where(
                Scan.repository_id == repository_id,
                Scan.scan_type == ScanType.AI_ADVISOR.value,
                Scan.status.notin_(list(_TERMINAL)),
            )
        )
        .scalars()
        .first()
    )
    if active is not None:
        logger.info(
            "ai_advisor_already_active",
            repository_id=str(repository_id),
            scan_id=str(active.id),
        )
        return active

    # Recovered Repository Scans must not spawn a second AI job for the same parent.
    if parent_scan_id is not None:
        from app.services.scan_recovery import parent_already_has_ai_advisor

        existing_for_parent = parent_already_has_ai_advisor(session, parent_scan_id)
        if existing_for_parent is not None:
            logger.info(
                "ai_advisor_already_linked_to_parent",
                repository_id=str(repository_id),
                scan_id=str(existing_for_parent.id),
                parent_scan_id=str(parent_scan_id),
            )
            return existing_for_parent

    repo = session.get(Repository, repository_id)
    job = Scan(
        repository_id=repository_id,
        triggered_by_user_id=triggered_by_user_id,
        scan_type=ScanType.AI_ADVISOR.value,
        status=ScanStatus.QUEUED.value,
        current_stage="queued",
        progress_percent=0,
        queued_at=_utcnow(),
        branch=repo.default_branch if repo else None,
        summary={
            "kind": "ai_upgrade_advisor",
            "parent_scan_id": str(parent_scan_id) if parent_scan_id else None,
        },
        extra_metadata={
            "kind": "ai_upgrade_advisor",
            "parent_scan_id": str(parent_scan_id) if parent_scan_id else None,
        },
    )
    session.add(job)
    session.flush()

    task = run_ai_upgrade_advisor.delay(str(job.id))
    job.celery_task_id = task.id
    session.flush()

    if parent_scan_id:
        parent = session.get(Scan, parent_scan_id)
        if parent is not None:
            summary = dict(parent.summary or {})
            summary["ai_advisor_scan_id"] = str(job.id)
            parent.summary = summary

    logger.info(
        "ai_advisor_enqueued",
        repository_id=str(repository_id),
        scan_id=str(job.id),
        parent_scan_id=str(parent_scan_id) if parent_scan_id else None,
    )
    return job


@celery_app.task(
    bind=True,
    name="app.services.tasks.ai_advisor_tasks.run_ai_upgrade_advisor",
    max_retries=2,
    soft_time_limit=getattr(_settings, "scan_soft_time_limit_seconds", 1800),
    time_limit=getattr(_settings, "scan_hard_time_limit_seconds", 2100),
)
def run_ai_upgrade_advisor(self, scan_id: str) -> dict[str, Any]:
    """Independent AI Upgrade Advisor job — never blocks Repository Scan."""
    session = SyncSessionLocal()
    owner_task_id = getattr(getattr(self, "request", None), "id", None)
    started = _utcnow()
    try:
        scan = session.get(Scan, UUID(scan_id))
        if scan is None:
            return {"error": "not_found"}
        if scan.scan_type != ScanType.AI_ADVISOR.value:
            return {"error": "not_ai_advisor_job"}
        if scan.cancel_requested or scan.status == ScanStatus.CANCELLED.value:
            return {"scan_id": scan_id, "status": "cancelled"}

        if (
            owner_task_id
            and scan.celery_task_id
            and scan.celery_task_id != owner_task_id
            and scan.status
            not in {ScanStatus.QUEUED.value, ScanStatus.PENDING.value}
        ):
            return {"scan_id": scan_id, "status": "superseded"}

        scan.celery_task_id = owner_task_id or scan.celery_task_id
        scan.status = ScanStatus.RUNNING.value
        scan.started_at = scan.started_at or started
        scan.last_heartbeat_at = started
        scan.worker_name = getattr(getattr(self, "request", None), "hostname", None)
        scan.current_stage = "preparing"
        scan.progress_percent = 10
        scan.stage_timings = record_stage_timing(
            scan.stage_timings, "preparing", now=started
        )
        session.commit()

        if not org_supports_ai_advisor(session, scan.repository_id):
            scan.status = ScanStatus.CANCELLED.value
            scan.current_stage = "cancelled"
            scan.error_message = "AI Upgrade Advisor is not available on the current plan."
            scan.completed_at = _utcnow()
            scan.progress_percent = 100
            session.commit()
            return {"scan_id": scan_id, "status": "cancelled", "reason": "plan"}

        def on_progress(stage: str, percent: int) -> None:
            s = session.get(Scan, UUID(scan_id))
            if s is None:
                return
            now = _utcnow()
            s.current_stage = stage
            s.progress_percent = percent
            s.last_heartbeat_at = now
            s.status = ScanStatus.ANALYZING_AI.value
            s.stage_timings = record_stage_timing(
                s.stage_timings, stage, now=now
            )
            session.commit()

        def should_cancel() -> bool:
            s = session.get(Scan, UUID(scan_id))
            if s is None:
                return True
            session.refresh(s)
            if s.cancel_requested or s.status == ScanStatus.CANCELLED.value:
                return True
            if (
                owner_task_id
                and s.celery_task_id
                and s.celery_task_id != owner_task_id
            ):
                return True
            return False

        result = run_ai_upgrade_advisor_for_repository(
            session,
            scan.repository_id,
            ai=AIAnalyzer(),
            on_progress=on_progress,
            should_cancel=should_cancel,
        )

        scan = session.get(Scan, UUID(scan_id))
        if scan is None:
            return result
        completed = _utcnow()
        if result.get("status") == "cancelled" or should_cancel():
            scan.status = ScanStatus.CANCELLED.value
            scan.current_stage = "cancelled"
            scan.completed_at = completed
            scan.stage_timings = close_stage_timings(scan.stage_timings, now=completed)
            session.commit()
            return {"scan_id": scan_id, "status": "cancelled", **result}

        scan.status = ScanStatus.COMPLETED.value
        scan.current_stage = "completed"
        scan.progress_percent = 100
        scan.completed_at = completed
        scan.duration_seconds = (completed - (scan.started_at or started)).total_seconds()
        scan.stage_timings = close_stage_timings(scan.stage_timings, now=completed)
        summary = dict(scan.summary or {})
        summary.update(
            {
                "kind": "ai_upgrade_advisor",
                "processed": result.get("processed"),
                "total": result.get("total"),
            }
        )
        scan.summary = summary
        session.commit()
        logger.info(
            "ai_advisor_completed",
            scan_id=scan_id,
            processed=result.get("processed"),
            total=result.get("total"),
        )
        return {"scan_id": scan_id, "status": "completed", **result}

    except Exception as exc:
        session.rollback()
        logger.exception("ai_advisor_failed", scan_id=scan_id, error=str(exc))
        try:
            scan = session.get(Scan, UUID(scan_id))
            if scan:
                scan.status = ScanStatus.FAILED.value
                scan.current_stage = "failed"
                scan.error_message = str(exc)[:2000]
                scan.error_traceback = traceback.format_exc()[-4000:]
                scan.completed_at = _utcnow()
                # Never mark repository sync as error — Repository Scan already succeeded
                session.commit()
        except Exception:  # noqa: BLE001
            session.rollback()
        raise
    finally:
        session.close()
