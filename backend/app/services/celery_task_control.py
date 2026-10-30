"""Helpers for safely revoking / waiting on Celery tasks."""

from __future__ import annotations

import time
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


def revoke_and_wait(
    task_id: Optional[str],
    *,
    timeout_seconds: float = 90.0,
    poll_interval: float = 0.5,
) -> bool:
    """
    Revoke a Celery task (terminate) and wait until it is no longer active.

    Returns True if the task is gone (or was never set), False on timeout.
    """
    if not task_id:
        return True

    try:
        from app.core.celery_app import celery_app
        from celery.result import AsyncResult
    except Exception as exc:  # noqa: BLE001
        logger.warning("celery_revoke_import_failed", error=str(exc))
        return False

    try:
        celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
    except Exception as exc:  # noqa: BLE001
        logger.warning("celery_revoke_failed", task_id=task_id, error=str(exc))

    deadline = time.monotonic() + max(1.0, timeout_seconds)
    while time.monotonic() < deadline:
        try:
            state = AsyncResult(task_id, app=celery_app).state
            if state in {"SUCCESS", "FAILURE", "REVOKED", "REJECTED"}:
                # Brief settle so GPU/HTTP work from the killed worker can release.
                time.sleep(0.75)
                return True
        except Exception:  # noqa: BLE001
            pass

        if not _task_in_active_or_reserved(task_id):
            time.sleep(0.75)
            return True
        time.sleep(poll_interval)

    logger.warning("celery_revoke_wait_timeout", task_id=task_id, timeout=timeout_seconds)
    return False


def _task_in_active_or_reserved(task_id: str) -> bool:
    try:
        from app.core.celery_app import celery_app

        insp = celery_app.control.inspect(timeout=1.0)
        if insp is None:
            return False
        for bucket in (insp.active() or {}, insp.reserved() or {}):
            for tasks in bucket.values():
                for item in tasks or []:
                    if str(item.get("id") or "") == task_id:
                        return True
    except Exception:  # noqa: BLE001
        return False
    return False
