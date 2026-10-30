"""Lightweight checks for lifecycle helpers (no DB)."""

from app.services.repository_lifecycle import ACTIVE_SCAN_STATUSES, ACTIVE_SIMULATION_STATUSES


def test_active_scan_statuses_include_classifying():
    assert "classifying" in ACTIVE_SCAN_STATUSES
    assert "queued" in ACTIVE_SCAN_STATUSES
    assert "completed" not in ACTIVE_SCAN_STATUSES


def test_active_simulation_statuses_exclude_terminal():
    assert "queued" in ACTIVE_SIMULATION_STATUSES
    assert "cancelled" not in ACTIVE_SIMULATION_STATUSES
    assert "failed" not in ACTIVE_SIMULATION_STATUSES
