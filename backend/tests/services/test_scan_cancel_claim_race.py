"""Regression C3: cancellation must always win over scan pickup."""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock
from uuid import uuid4

from app.core.enums import ScanStatus
from app.services.tasks.scan_tasks import _try_claim_scan, run_repository_scan


def test_pickup_never_clears_cancel_requested() -> None:
    src = inspect.getsource(run_repository_scan)
    assert "cancel_requested = False" not in src
    assert "_try_claim_scan" in src


def test_try_claim_scan_update_predicate_includes_cancel_guard() -> None:
    src = inspect.getsource(_try_claim_scan)
    assert "cancel_requested.is_(False)" in src
    assert "TERMINAL_SCAN_STATUSES" in src
    # Claim must not write cancel_requested=False
    assert "cancel_requested\": False" not in src
    assert "cancel_requested=False" not in src


def test_try_claim_scan_returns_false_when_update_matches_nothing() -> None:
    session = MagicMock()
    result = MagicMock()
    result.rowcount = 0
    session.execute.return_value = result

    scan = MagicMock()
    scan.id = uuid4()
    scan.progress_percent = 0
    scan.started_at = None
    scan.stage_timings = []
    scan.status = ScanStatus.QUEUED.value
    scan.cancel_requested = True

    ok = _try_claim_scan(
        session,
        scan,
        owner_task_id="task-1",
        worker_name="worker@test",
    )
    assert ok is False
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(scan)


def test_try_claim_scan_returns_true_on_rowcount_one() -> None:
    session = MagicMock()
    result = MagicMock()
    result.rowcount = 1
    session.execute.return_value = result

    scan = MagicMock()
    scan.id = uuid4()
    scan.progress_percent = 0
    scan.started_at = None
    scan.stage_timings = []

    ok = _try_claim_scan(
        session,
        scan,
        owner_task_id="task-1",
        worker_name="worker@test",
        retry_count=1,
    )
    assert ok is True
