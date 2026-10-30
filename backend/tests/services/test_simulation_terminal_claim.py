"""Regression C2: completed/failed simulations must never be re-claimed."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.enums import SimulationStatus
from app.services.tasks.upgrade_simulation_tasks import (
    TERMINAL_SIMULATION_STATUSES,
    _simulation_is_terminal,
)


@pytest.mark.parametrize(
    "status,terminal",
    [
        (SimulationStatus.COMPLETED.value, True),
        (SimulationStatus.FAILED.value, True),
        (SimulationStatus.CANCELLED.value, True),
        (SimulationStatus.QUEUED.value, False),
        (SimulationStatus.COLLECTING_SOURCES.value, False),
    ],
)
def test_simulation_is_terminal(status: str, terminal: bool) -> None:
    assert _simulation_is_terminal(SimpleNamespace(status=status)) is terminal


def test_terminal_set_covers_completed_failed_cancelled() -> None:
    assert SimulationStatus.COMPLETED.value in TERMINAL_SIMULATION_STATUSES
    assert SimulationStatus.FAILED.value in TERMINAL_SIMULATION_STATUSES
    assert SimulationStatus.CANCELLED.value in TERMINAL_SIMULATION_STATUSES


def test_pickup_guard_before_progress_mutation() -> None:
    import inspect
    from app.services.tasks.upgrade_simulation_tasks import run_upgrade_simulation

    src = inspect.getsource(run_upgrade_simulation)
    term_idx = src.find("_simulation_is_terminal")
    progress_idx = src.find("COLLECTING_SOURCES")
    assert term_idx != -1
    assert progress_idx != -1
    assert term_idx < progress_idx
