"""Repository Scan automatic recovery after unexpected worker death."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.core.enums import ScanStatus, ScanType
from app.services import scan_recovery as recovery
from app.services.job_health import classify_job
from app.services.scan_recovery import (
    RECOVERING_MESSAGE,
    RECOVERING_STAGE,
    fail_recovery_exhausted,
    is_recovering,
    parent_already_has_ai_advisor,
    recovery_count,
    try_recover_abandoned_repository_scan,
)


def _scan(**overrides):
    now = datetime.now(timezone.utc)
    base = {
        "id": uuid4(),
        "repository_id": uuid4(),
        "scan_type": ScanType.MANUAL.value,
        "status": ScanStatus.CHECKING_LICENSES.value,
        "celery_task_id": "dead-task-1",
        "worker_name": "celery@worker-a",
        "cancel_requested": False,
        "retry_count": 0,
        "progress_percent": 88,
        "current_stage": "knowledge",
        "error_message": None,
        "error_traceback": None,
        "started_at": now - timedelta(minutes=10),
        "completed_at": None,
        "duration_seconds": None,
        "queued_at": now - timedelta(minutes=12),
        "last_heartbeat_at": now - timedelta(minutes=10),
        "stage_timings": [{"stage": "knowledge", "started_at": now.isoformat()}],
        "extra_metadata": {},
        "summary": {},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_classify_heartbeat_lost_still_detects_abandoned_worker() -> None:
    now = datetime.now(timezone.utc)
    verdict = classify_job(
        status=ScanStatus.CHECKING_LICENSES.value,
        terminal_statuses={
            ScanStatus.COMPLETED.value,
            ScanStatus.FAILED.value,
            ScanStatus.CANCELLED.value,
        },
        pending_statuses={ScanStatus.PENDING.value, ScanStatus.QUEUED.value},
        queued_at=now - timedelta(minutes=20),
        started_at=now - timedelta(minutes=15),
        last_heartbeat_at=now - timedelta(minutes=10),
        pickup_timeout_seconds=60,
        running_timeout_minutes=30,
        worker_online=True,
        now=now,
    )
    assert verdict.state == "heartbeat_lost"


def test_recovery_cas_lost_is_idempotent() -> None:
    session = MagicMock()
    result = MagicMock()
    result.rowcount = 0
    session.execute.return_value = result
    scan = _scan()

    outcome = try_recover_abandoned_repository_scan(session, scan)
    assert outcome == "skipped"
    session.rollback.assert_called()


def test_recovery_succeeds_once_and_records_metadata() -> None:
    session = MagicMock()
    cas = MagicMock(rowcount=1)
    attach = MagicMock(rowcount=1)
    session.execute.side_effect = [cas, attach]
    scan = _scan()
    session.get.return_value = SimpleNamespace(
        id=scan.repository_id, sync_status="syncing"
    )

    with patch(
        "app.services.tasks.scan_tasks.run_repository_scan"
    ) as task_mod:
        task_mod.delay.return_value = SimpleNamespace(id="new-task-9")
        with patch.object(recovery, "_revoke") as revoke:
            outcome = try_recover_abandoned_repository_scan(session, scan)

    assert outcome == "recovered"
    revoke.assert_called_once_with("dead-task-1")
    task_mod.delay.assert_called_once_with(str(scan.id))
    assert session.execute.call_count == 2  # reclaim CAS + attach new task id
    assert session.commit.call_count >= 2
    assert session.refresh.call_count >= 1


def test_recovery_exhausted_after_budget() -> None:
    scan = _scan(
        extra_metadata={
            "recovery": {
                "recovery_count": 2,
                "recovered_from_worker_failure": True,
            }
        }
    )
    assert recovery_count(scan) == 2
    with patch.object(recovery, "max_recoveries", return_value=2):
        session = MagicMock()
        outcome = try_recover_abandoned_repository_scan(session, scan)
    assert outcome == "exhausted"
    session.execute.assert_not_called()


def test_recovery_skips_ai_advisor_and_terminal_and_queued() -> None:
    session = MagicMock()
    assert (
        try_recover_abandoned_repository_scan(
            session, _scan(scan_type=ScanType.AI_ADVISOR.value)
        )
        == "skipped"
    )
    assert (
        try_recover_abandoned_repository_scan(
            session, _scan(status=ScanStatus.COMPLETED.value)
        )
        == "skipped"
    )
    assert (
        try_recover_abandoned_repository_scan(
            session, _scan(status=ScanStatus.QUEUED.value)
        )
        == "skipped"
    )


def test_is_recovering_banner() -> None:
    scan = _scan(
        status=ScanStatus.QUEUED.value,
        current_stage=RECOVERING_STAGE,
        error_message=RECOVERING_MESSAGE,
        celery_task_id="new-task",
        started_at=None,
    )
    assert is_recovering(scan) is True


def test_fail_recovery_exhausted_message() -> None:
    session = MagicMock()
    scan = _scan()
    repo = SimpleNamespace(id=scan.repository_id, sync_status="error")
    session.get.return_value = repo
    with patch.object(recovery, "_revoke"), patch(
        "app.services.repository_counters.sync_repository_counters"
    ) as sync_counters:
        fail_recovery_exhausted(session, scan)
    assert scan.status == ScanStatus.FAILED.value
    assert "Automatic recovery could not complete" in (scan.error_message or "")
    assert RECOVERING_MESSAGE not in (scan.error_message or "")
    sync_counters.assert_called_once_with(session, repo)
    assert repo.sync_status == "error"


def test_parent_already_has_ai_advisor_prevents_duplicate() -> None:
    session = MagicMock()
    parent_id = uuid4()
    advisor_id = uuid4()
    parent = SimpleNamespace(
        id=parent_id,
        repository_id=uuid4(),
        summary={"ai_advisor_scan_id": str(advisor_id)},
    )
    advisor = SimpleNamespace(id=advisor_id)
    session.get.side_effect = lambda model, pk: (
        parent if pk == parent_id else advisor if pk == advisor_id else None
    )
    found = parent_already_has_ai_advisor(session, parent_id)
    assert found is advisor


def test_try_claim_clears_recovery_banner() -> None:
    from app.services.tasks.scan_tasks import _try_claim_scan

    src = __import__("inspect").getsource(_try_claim_scan)
    assert '"error_message": None' in src or "'error_message': None" in src


def test_scheduler_wires_heartbeat_recovery() -> None:
    from app.services.tasks import scheduled_tasks

    src = __import__("inspect").getsource(scheduled_tasks.cleanup_stale_scans)
    assert "try_recover_abandoned_repository_scan" in src
    assert "heartbeat_lost" in src
    assert "fail_recovery_exhausted" in src


def test_api_reconcile_wires_heartbeat_recovery() -> None:
    from app.api.v1 import scans as scans_api

    src = __import__("inspect").getsource(scans_api._reconcile_scan)
    assert "_auto_recover_heartbeat_lost" in src
    assert "heartbeat_lost" in src


def test_ai_enqueue_checks_parent_link() -> None:
    from app.services.tasks import ai_advisor_tasks

    src = __import__("inspect").getsource(ai_advisor_tasks.enqueue_ai_upgrade_advisor)
    assert "parent_already_has_ai_advisor" in src
