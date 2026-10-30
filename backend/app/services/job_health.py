"""Worker and queue health for background jobs.

Single source of truth for:
  * whether Celery workers are online
  * queue depth / blocked detection
  * queue position for a waiting job
  * stalled / timed-out job classification

Both the Repository Scan and Upgrade Simulator pipelines use these helpers so the
two features behave identically. All thresholds come from settings — never
hardcode timeouts at call sites.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Celery queues that carry user-visible background jobs.
SCAN_QUEUE = "scans"
ANALYSIS_QUEUE = "analysis"
JOB_QUEUES = (SCAN_QUEUE, ANALYSIS_QUEUE, "default", "notifications")

# Worker health changes slowly relative to the UI poll interval, and probing it
# is a blocking broadcast. Cache it so status polling stays cheap.
_HEALTH_CACHE: dict[bool, tuple[float, "WorkerHealth"]] = {}
_HEALTH_LOCK = threading.Lock()
_REFRESHING: set[bool] = set()


def reset_worker_health_cache() -> None:
    """Force the next probe to hit Celery. Used by tests and after failovers."""
    with _HEALTH_LOCK:
        _HEALTH_CACHE.clear()
        _REFRESHING.clear()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_aware(value: Optional[datetime]) -> Optional[datetime]:
    """Normalize naive DB timestamps to UTC-aware."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def age_seconds(value: Optional[datetime], *, now: Optional[datetime] = None) -> Optional[float]:
    aware = as_aware(value)
    if aware is None:
        return None
    return ((now or utcnow()) - aware).total_seconds()


@dataclass
class WorkerHealth:
    online: bool = False
    worker_count: int = 0
    workers: list[str] = field(default_factory=list)
    active_tasks: int = 0
    reserved_tasks: int = 0
    queue_depths: dict[str, int] = field(default_factory=dict)
    queue_blocked: bool = False
    detail: Optional[str] = None

    @property
    def queued_total(self) -> int:
        return sum(self.queue_depths.values())

    def to_dict(self) -> dict[str, Any]:
        settings = get_settings()
        return {
            "online": self.online,
            "status": self.status,
            "active_workers": self.worker_count,
            "workers": self.workers,
            "active_tasks": self.active_tasks,
            "reserved_tasks": self.reserved_tasks,
            "queue_depths": self.queue_depths,
            "queued_total": self.queued_total,
            "queue_blocked": self.queue_blocked,
            "detail": self.detail or self.message,
            "message": self.message,
            "heartbeat_seconds": settings.worker_heartbeat_seconds,
            "pickup_timeout_seconds": settings.scan_pickup_timeout_seconds,
            "stale_timeout_minutes": settings.stale_scan_timeout_minutes,
        }

    @property
    def status(self) -> str:
        if not self.online:
            return "offline"
        if self.queue_blocked:
            return "blocked"
        return "online"

    @property
    def message(self) -> str:
        if not self.online:
            return "Background processing service is unavailable."
        if self.queue_blocked:
            return "Background queue is congested. Jobs may take longer than usual."
        return "Background workers are online."


def _queue_depths() -> dict[str, int]:
    """Read pending message counts straight from the Redis broker lists."""
    depths: dict[str, int] = {}
    try:
        import redis  # type: ignore

        settings = get_settings()
        client = redis.Redis.from_url(settings.celery_broker_url, socket_timeout=1.5)
        for queue in JOB_QUEUES:
            try:
                depths[queue] = int(client.llen(queue) or 0)
            except Exception:  # noqa: BLE001
                continue
    except Exception as exc:  # noqa: BLE001
        logger.debug("queue_depth_unavailable", error=str(exc))
    return depths


def get_worker_health(
    *, timeout: Optional[float] = None, detailed: bool = True, use_cache: bool = True
) -> WorkerHealth:
    """
    Inspect Celery workers and broker queues. Never raises.

    Results are cached briefly because a Celery `inspect` is a broadcast RPC
    that blocks for up to `timeout` per call, and the UI polls job status every
    couple of seconds.

    Set `detailed=False` to skip the active/reserved round-trips when only
    online/offline matters.
    """
    settings = get_settings()
    probe_timeout = (
        timeout if timeout is not None else settings.worker_health_probe_timeout_seconds
    )

    if use_cache:
        entry = _HEALTH_CACHE.get(detailed)
        if entry is not None:
            cached_at, cached = entry
            if (time.monotonic() - cached_at) <= settings.worker_health_cache_seconds:
                return cached
            # Stale-while-revalidate: a broadcast inspect takes seconds, so serve
            # the last known verdict and refresh out of band. Health changes far
            # slower than the poll interval, so a few seconds of staleness is safe.
            _refresh_in_background(timeout=probe_timeout, detailed=detailed)
            return cached

    health = _probe_worker_health(timeout=probe_timeout, detailed=detailed)
    with _HEALTH_LOCK:
        _HEALTH_CACHE[detailed] = (time.monotonic(), health)
    return health


def _refresh_in_background(*, timeout: float, detailed: bool) -> None:
    with _HEALTH_LOCK:
        if detailed in _REFRESHING:
            return
        _REFRESHING.add(detailed)

    def worker() -> None:
        try:
            health = _probe_worker_health(timeout=timeout, detailed=detailed)
            with _HEALTH_LOCK:
                _HEALTH_CACHE[detailed] = (time.monotonic(), health)
        except Exception as exc:  # noqa: BLE001
            logger.debug("worker_health_refresh_failed", error=str(exc))
        finally:
            with _HEALTH_LOCK:
                _REFRESHING.discard(detailed)

    threading.Thread(target=worker, name="worker-health-refresh", daemon=True).start()


def _probe_worker_health(*, timeout: float, detailed: bool) -> WorkerHealth:
    settings = get_settings()
    health = WorkerHealth()
    health.queue_depths = _queue_depths()

    try:
        from app.core.celery_app import celery_app

        inspector = celery_app.control.inspect(timeout=timeout)
        ping = inspector.ping() or {}
        health.online = bool(ping)
        health.workers = sorted(ping.keys())
        health.worker_count = len(ping)

        if health.online and detailed:
            active = inspector.active() or {}
            reserved = inspector.reserved() or {}
            health.active_tasks = sum(len(v or []) for v in active.values())
            health.reserved_tasks = sum(len(v or []) for v in reserved.values())
    except Exception as exc:  # noqa: BLE001
        logger.warning("worker_inspect_failed", error=str(exc))
        health.online = False
        health.detail = "Unable to reach the background worker service."

    # Blocked = work is waiting while the workers have nothing in flight and
    # nothing reserved. Checking `reserved` too avoids flagging the normal
    # moment between a task being published and a worker claiming it.
    waiting = health.queued_total
    if (
        health.online
        and detailed
        and waiting > 0
        and health.active_tasks == 0
        and health.reserved_tasks == 0
    ):
        health.queue_blocked = True
    elif waiting >= settings.queue_blocked_depth_threshold:
        health.queue_blocked = True

    return health


@dataclass
class JobLifecycle:
    """Derived lifecycle verdict for a queued or running job."""

    state: str  # waiting | running | stalled | pickup_timeout | heartbeat_lost | run_timeout
    message: Optional[str] = None

    @property
    def is_unhealthy(self) -> bool:
        return self.state in {"pickup_timeout", "heartbeat_lost", "run_timeout"}

    @property
    def is_stalled(self) -> bool:
        return self.state == "stalled"


def classify_job(
    *,
    status: str,
    terminal_statuses: set[str],
    pending_statuses: set[str],
    queued_at: Optional[datetime],
    started_at: Optional[datetime],
    last_heartbeat_at: Optional[datetime],
    pickup_timeout_seconds: int,
    running_timeout_minutes: int,
    worker_online: bool,
    now: Optional[datetime] = None,
) -> JobLifecycle:
    """
    Classify a job purely from timestamps + worker availability.

    Kept free of ORM types so scans and simulations can share it.
    """
    settings = get_settings()
    now = now or utcnow()

    if status in terminal_statuses:
        return JobLifecycle(state="terminal")

    if status in pending_statuses and started_at is None:
        waited = age_seconds(queued_at, now=now) or 0.0
        if waited > pickup_timeout_seconds:
            if not worker_online:
                return JobLifecycle(
                    state="pickup_timeout",
                    message="Background processing service is unavailable.",
                )
            return JobLifecycle(
                state="pickup_timeout",
                message=(
                    "No worker picked up this job in "
                    f"{pickup_timeout_seconds}s. The queue may be blocked."
                ),
            )
        # Waiting, but still within the pickup window. Surface "stalled" early so
        # the UI can explain the delay without failing the job.
        if waited > max(pickup_timeout_seconds / 2, 30):
            return JobLifecycle(
                state="stalled",
                message="Waiting longer than usual for an available worker.",
            )
        return JobLifecycle(state="waiting")

    # Running: heartbeat and total runtime guards.
    runtime = age_seconds(started_at, now=now)
    if runtime is not None and runtime > running_timeout_minutes * 60:
        return JobLifecycle(
            state="run_timeout",
            message=f"Job exceeded the {running_timeout_minutes} minute time limit.",
        )

    since_beat = age_seconds(last_heartbeat_at, now=now)
    if since_beat is not None and since_beat > settings.stale_scan_timeout_minutes * 60:
        return JobLifecycle(
            state="heartbeat_lost",
            message="Worker stopped responding while processing this job.",
        )

    return JobLifecycle(state="running")


def heartbeat_is_due(
    last_heartbeat_at: Optional[datetime], *, now: Optional[datetime] = None
) -> bool:
    """True when the worker should persist a new heartbeat."""
    settings = get_settings()
    if last_heartbeat_at is None:
        return True
    elapsed = age_seconds(last_heartbeat_at, now=now) or 0.0
    return elapsed >= settings.worker_heartbeat_seconds


def record_stage_timing(
    timings: Optional[list], stage: str, *, now: Optional[datetime] = None
) -> list:
    """
    Append/close stage timing entries.

    Closes the previous open stage and opens a new one, producing an auditable
    per-stage duration trail for observability.
    """
    now = now or utcnow()
    entries = list(timings or [])
    if entries:
        last = dict(entries[-1])
        if not last.get("completed_at"):
            last["completed_at"] = now.isoformat()
            started = last.get("started_at")
            if started:
                try:
                    began = datetime.fromisoformat(started)
                    last["duration_seconds"] = round((now - began).total_seconds(), 2)
                except ValueError:
                    pass
            entries[-1] = last
        if last.get("stage") == stage:
            return entries

    entries.append({"stage": stage, "started_at": now.isoformat()})
    # Keep the trail bounded — pipelines have ~12 stages, retries can add more.
    return entries[-40:]


def close_stage_timings(timings: Optional[list], *, now: Optional[datetime] = None) -> list:
    """Close the final open stage when a job reaches a terminal state."""
    now = now or utcnow()
    entries = list(timings or [])
    if not entries:
        return entries
    last = dict(entries[-1])
    if not last.get("completed_at"):
        last["completed_at"] = now.isoformat()
        started = last.get("started_at")
        if started:
            try:
                began = datetime.fromisoformat(started)
                last["duration_seconds"] = round((now - began).total_seconds(), 2)
            except ValueError:
                pass
        entries[-1] = last
    return entries
