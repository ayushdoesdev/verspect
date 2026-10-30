"""Regression H1: Celery publish must happen after durable commit."""

from __future__ import annotations

import inspect

from app.api.v1 import dependencies as deps_api
from app.api.v1 import scans as scans_api
from app.api.v1 import webhooks as webhooks_api
from app.services.tasks import scheduled_tasks


def test_trigger_scan_commits_before_dispatch() -> None:
    src = inspect.getsource(scans_api.trigger_scan)
    commit_idx = src.find("await db.commit()")
    dispatch_idx = src.find("await _dispatch_scan")
    assert commit_idx != -1 and dispatch_idx != -1
    assert commit_idx < dispatch_idx


def test_webhook_commits_before_delay() -> None:
    src = inspect.getsource(webhooks_api.github_webhook)
    # Both push and release paths commit then delay
    assert src.count("await db.commit()") >= 2
    assert src.find("await db.commit()") < src.find(".delay(")


def test_scheduled_tasks_commit_before_delay() -> None:
    daily = inspect.getsource(scheduled_tasks.daily_rescan_all)
    hourly = inspect.getsource(scheduled_tasks.hourly_version_check)
    for src in (daily, hourly):
        # flush → commit → delay
        flush_i = src.find("session.flush()")
        # first commit after flush in the loop body
        commit_i = src.find("session.commit()", flush_i)
        delay_i = src.find(".delay(", flush_i)
        assert flush_i != -1 and commit_i != -1 and delay_i != -1
        assert commit_i < delay_i


def test_simulate_upgrade_commits_before_delay() -> None:
    src = inspect.getsource(deps_api.simulate_upgrade)
    # Durable commit marker precedes delay in created branch
    assert "Durable row before Celery publish" in src
    commit_i = src.find("sync_db.commit()")
    delay_i = src.find("run_upgrade_simulation.delay")
    assert commit_i != -1 and delay_i != -1
    assert commit_i < delay_i
