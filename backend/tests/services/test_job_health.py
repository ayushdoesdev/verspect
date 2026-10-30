"""Lifecycle classification for background jobs (scans + upgrade simulations)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.job_health import (
    JOB_QUEUES,
    WorkerHealth,
    age_seconds,
    as_aware,
    classify_job,
    close_stage_timings,
    heartbeat_is_due,
    record_stage_timing,
)

TERMINAL = {"completed", "failed", "cancelled"}
PENDING = {"pending", "queued"}


def _classify(**overrides):
    now = datetime.now(timezone.utc)
    kwargs = {
        "status": "queued",
        "terminal_statuses": TERMINAL,
        "pending_statuses": PENDING,
        "queued_at": now,
        "started_at": None,
        "last_heartbeat_at": None,
        "pickup_timeout_seconds": 60,
        "running_timeout_minutes": 30,
        "worker_online": True,
        "now": now,
    }
    kwargs.update(overrides)
    return classify_job(**kwargs)


def test_terminal_jobs_are_never_reaped():
    for status in TERMINAL:
        assert _classify(status=status).state == "terminal"


def test_freshly_queued_job_is_waiting():
    assert _classify().state == "waiting"


def test_long_wait_is_reported_as_stalled_before_failing():
    now = datetime.now(timezone.utc)
    verdict = _classify(queued_at=now - timedelta(seconds=45), now=now)
    assert verdict.state == "stalled"
    assert not verdict.is_unhealthy


def test_pickup_timeout_fails_the_job():
    now = datetime.now(timezone.utc)
    verdict = _classify(queued_at=now - timedelta(seconds=90), now=now)
    assert verdict.state == "pickup_timeout"
    assert verdict.is_unhealthy


def test_pickup_timeout_message_explains_offline_worker():
    now = datetime.now(timezone.utc)
    verdict = _classify(
        queued_at=now - timedelta(seconds=90), worker_online=False, now=now
    )
    assert verdict.state == "pickup_timeout"
    assert "unavailable" in (verdict.message or "")


def test_running_job_with_recent_heartbeat_is_healthy():
    now = datetime.now(timezone.utc)
    verdict = _classify(
        status="running",
        started_at=now - timedelta(minutes=2),
        last_heartbeat_at=now - timedelta(seconds=5),
        now=now,
    )
    assert verdict.state == "running"
    assert not verdict.is_unhealthy


def test_lost_heartbeat_marks_job_unhealthy():
    now = datetime.now(timezone.utc)
    verdict = _classify(
        status="running",
        started_at=now - timedelta(minutes=3),
        last_heartbeat_at=now - timedelta(minutes=10),
        now=now,
    )
    assert verdict.state == "heartbeat_lost"
    assert verdict.is_unhealthy


def test_run_timeout_takes_priority_over_heartbeat():
    now = datetime.now(timezone.utc)
    verdict = _classify(
        status="running",
        started_at=now - timedelta(minutes=45),
        last_heartbeat_at=now - timedelta(seconds=1),
        running_timeout_minutes=30,
        now=now,
    )
    assert verdict.state == "run_timeout"
    assert verdict.is_unhealthy


def test_naive_timestamps_are_treated_as_utc():
    now = datetime.now(timezone.utc)
    naive = (now - timedelta(seconds=90)).replace(tzinfo=None)
    verdict = _classify(queued_at=naive, now=now)
    assert verdict.state == "pickup_timeout"


def test_heartbeat_is_due_when_never_recorded():
    assert heartbeat_is_due(None) is True


def test_heartbeat_not_due_immediately_after_write():
    assert heartbeat_is_due(datetime.now(timezone.utc)) is False


def test_stage_timings_close_previous_stage():
    timings = record_stage_timing([], "cloning")
    timings = record_stage_timing(timings, "manifests")

    assert [t["stage"] for t in timings] == ["cloning", "manifests"]
    assert timings[0]["completed_at"] is not None
    assert timings[0]["duration_seconds"] >= 0
    assert "completed_at" not in timings[1]


def test_repeating_the_same_stage_does_not_duplicate_entries():
    timings = record_stage_timing([], "cloning")
    timings = record_stage_timing(timings, "cloning")
    assert len(timings) == 1


def test_close_stage_timings_finalizes_open_stage():
    timings = close_stage_timings(record_stage_timing([], "ai"))
    assert timings[-1]["completed_at"] is not None


def test_worker_health_reports_offline_message():
    health = WorkerHealth()
    assert health.status == "offline"
    assert "unavailable" in health.message


def test_worker_health_reports_blocked_queue():
    health = WorkerHealth(online=True, worker_count=1, queue_blocked=True)
    assert health.status == "blocked"
    assert "congested" in health.message


def test_worker_health_dict_exposes_configured_thresholds():
    payload = WorkerHealth(online=True, worker_count=1).to_dict()
    assert payload["status"] == "online"
    assert payload["heartbeat_seconds"] > 0
    assert payload["pickup_timeout_seconds"] > 0


def test_job_queues_cover_scan_and_analysis():
    assert "scans" in JOB_QUEUES
    assert "analysis" in JOB_QUEUES


@pytest.mark.parametrize("value", [None])
def test_age_seconds_handles_missing_timestamps(value):
    assert age_seconds(value) is None
    assert as_aware(value) is None
