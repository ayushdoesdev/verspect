"""Regression C1: completed/failed scans must never be re-claimed."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.enums import ScanStatus
from app.services.tasks.scan_tasks import TERMINAL_SCAN_STATUSES, _scan_is_terminal


@pytest.mark.parametrize(
    "status,terminal",
    [
        (ScanStatus.COMPLETED.value, True),
        (ScanStatus.FAILED.value, True),
        (ScanStatus.CANCELLED.value, True),
        (ScanStatus.QUEUED.value, False),
        (ScanStatus.RUNNING.value, False),
        (ScanStatus.CHECKING_VERSIONS.value, False),
    ],
)
def test_scan_is_terminal(status: str, terminal: bool) -> None:
    scan = SimpleNamespace(status=status)
    assert _scan_is_terminal(scan) is terminal


def test_terminal_set_covers_completed_failed_cancelled() -> None:
    assert ScanStatus.COMPLETED.value in TERMINAL_SCAN_STATUSES
    assert ScanStatus.FAILED.value in TERMINAL_SCAN_STATUSES
    assert ScanStatus.CANCELLED.value in TERMINAL_SCAN_STATUSES
    assert ScanStatus.QUEUED.value not in TERMINAL_SCAN_STATUSES


def test_pickup_guard_order_in_run_repository_scan() -> None:
    """Terminal check must run before claim mutates the row."""
    import inspect
    from app.services.tasks.scan_tasks import run_repository_scan

    src = inspect.getsource(run_repository_scan)
    term_idx = src.find("_scan_is_terminal")
    claim_idx = src.find("_try_claim_scan")
    assert term_idx != -1
    assert claim_idx != -1
    assert term_idx < claim_idx
