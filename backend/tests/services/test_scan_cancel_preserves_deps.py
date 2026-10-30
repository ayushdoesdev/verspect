"""Cancel checkpoints must not discard unflushed dependency mutations."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from app.services.tasks.scan_tasks import _is_scan_cancelled


def test_is_scan_cancelled_does_not_call_expire_all():
    session = MagicMock()
    scan_id = str(uuid4())
    scan = MagicMock()
    scan.id = scan_id
    scan.celery_task_id = "task-1"
    scan.cancel_requested = False
    scan.status = "analyzing_ai"
    session.get.return_value = scan

    result = _is_scan_cancelled(session, scan_id, owner_task_id="task-1")

    assert result is False
    session.expire_all.assert_not_called()
    session.refresh.assert_called_once_with(scan)
