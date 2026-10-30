"""Repository counters must match dependency rows after cancel/fail."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.core.enums import LicensePolicyAction, RepositorySyncStatus, ScanStatus
from app.services.repository_counters import apply_repository_counters_from_dependencies
from app.services.tasks.scan_tasks import _fail_scan, _is_scan_cancelled


def _dep(**kwargs):
    defaults = dict(
        is_outdated=False,
        has_vulnerabilities=False,
        license_policy_action=None,
        critical_vuln_count=0,
        health_score=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_apply_counters_from_partial_enrichment():
    repo = SimpleNamespace(
        dependency_count=0,
        outdated_count=0,
        vulnerable_count=0,
        license_issues_count=0,
        critical_alert_count=0,
        warning_count=0,
        health_score=None,
    )
    deps = [
        _dep(is_outdated=True, health_score=80.0),
        _dep(has_vulnerabilities=True, critical_vuln_count=2, health_score=40.0),
        _dep(license_policy_action=LicensePolicyAction.REJECT.value),
        _dep(),
    ]

    apply_repository_counters_from_dependencies(repo, deps)

    assert repo.dependency_count == 4
    assert repo.outdated_count == 1
    assert repo.vulnerable_count == 1
    assert repo.license_issues_count == 1
    assert repo.critical_alert_count == 1
    assert repo.warning_count == 2
    assert repo.health_score == 60.0


def test_apply_counters_empty_deps_zeros_repo():
    repo = SimpleNamespace(
        dependency_count=9,
        outdated_count=2,
        vulnerable_count=1,
        license_issues_count=1,
        critical_alert_count=1,
        warning_count=3,
        health_score=70.0,
    )
    apply_repository_counters_from_dependencies(repo, [])
    assert repo.dependency_count == 0
    assert repo.outdated_count == 0
    assert repo.vulnerable_count == 0
    assert repo.license_issues_count == 0
    assert repo.critical_alert_count == 0
    assert repo.warning_count == 0
    assert repo.health_score is None


def test_midflight_cancel_syncs_repository_counters(monkeypatch):
    session = MagicMock()
    scan_id = str(uuid4())
    repo_id = uuid4()
    scan = MagicMock()
    scan.id = scan_id
    scan.celery_task_id = "task-1"
    scan.cancel_requested = True
    scan.status = ScanStatus.CHECKING_VERSIONS.value
    scan.repository_id = repo_id
    scan.stage_timings = []
    repo = MagicMock()
    repo.id = repo_id

    def _get(model, _key):
        name = getattr(model, "__name__", str(model))
        if "Scan" in name:
            return scan
        return repo

    session.get.side_effect = _get

    called: dict = {}

    def fake_sync(sess, r):
        called["repo"] = r
        called["session"] = sess

    monkeypatch.setattr(
        "app.services.repository_counters.sync_repository_counters",
        fake_sync,
    )

    assert _is_scan_cancelled(session, scan_id, owner_task_id="task-1") is True
    assert called["repo"] is repo
    assert called["session"] is session
    assert scan.status == ScanStatus.CANCELLED.value
    assert repo.sync_status == RepositorySyncStatus.IDLE.value
    session.commit.assert_called()


def test_fail_scan_syncs_repository_counters(monkeypatch):
    session = MagicMock()
    scan = MagicMock()
    scan.id = uuid4()
    scan.stage_timings = []
    scan.started_at = None
    scan.duration_seconds = None
    scan.worker_name = "w"
    scan.retry_count = 0
    scan.current_stage = "versions"
    repo = MagicMock()

    called: dict = {}

    def fake_sync(sess, r):
        called["ok"] = True
        called["repo"] = r

    monkeypatch.setattr(
        "app.services.repository_counters.sync_repository_counters",
        fake_sync,
    )

    _fail_scan(session, scan, repo, "boom")
    assert called["ok"] is True
    assert called["repo"] is repo
    assert repo.sync_status == RepositorySyncStatus.ERROR.value
    session.commit.assert_called()
