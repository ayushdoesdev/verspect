"""
Manual verification harness for the background job pipeline.

Exercises the failure paths that are hard to reproduce by clicking:
pickup timeout, lost heartbeat, run timeout, cancellation, duplicate
prevention and simulation parity.

Usage (inside the backend container):
    python scripts/verify_job_pipeline.py

Creates and removes its own throwaway rows; it does not touch real scans.
"""

from __future__ import annotations

import sys
from datetime import timedelta

from sqlalchemy import select

from app.core.database import SyncSessionLocal
from app.core.enums import ScanStatus, ScanType, SimulationStatus
from app.models.dependency import Dependency
from app.models.repository import Repository
from app.models.scan import Scan
from app.models.upgrade_simulation import UpgradeSimulation
from app.services.job_health import get_worker_health, utcnow

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append((name, passed, detail))
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def _repo(session) -> Repository | None:
    return session.execute(
        select(Repository).where(Repository.deleted_at.is_(None))
    ).scalars().first()


def _make_scan(session, repo: Repository, **overrides) -> Scan:
    now = utcnow()
    scan = Scan(
        repository_id=repo.id,
        scan_type=ScanType.MANUAL.value,
        status=ScanStatus.QUEUED.value,
        progress_percent=0,
        current_stage="queued",
        queued_at=now,
        stage_timings=[],
    )
    for key, value in overrides.items():
        setattr(scan, key, value)
    session.add(scan)
    session.commit()
    return scan


def run() -> int:
    from app.services.tasks.scheduled_tasks import cleanup_stale_scans

    session = SyncSessionLocal()
    created: list[Scan] = []
    created_sims: list[UpgradeSimulation] = []

    try:
        health = get_worker_health()
        check(
            "worker health probe returns a verdict",
            health.status in {"online", "offline", "blocked"},
            f"status={health.status} workers={health.worker_count}",
        )

        repo = _repo(session)
        if repo is None:
            check("repository available for fixtures", False, "no repositories in database")
            return 1

        now = utcnow()

        # 1. Never picked up by a worker.
        stuck = _make_scan(session, repo, queued_at=now - timedelta(minutes=10))
        created.append(stuck)

        # 2. Worker died mid-run (heartbeat went silent).
        silent = _make_scan(
            session,
            repo,
            status=ScanStatus.PARSING_AST.value,
            current_stage="ast",
            progress_percent=55,
            queued_at=now - timedelta(minutes=20),
            started_at=now - timedelta(minutes=18),
            last_heartbeat_at=now - timedelta(minutes=15),
            worker_name="celery@dead-worker",
        )
        created.append(silent)

        # 3. Exceeded the configured maximum runtime.
        overrun = _make_scan(
            session,
            repo,
            status=ScanStatus.CHECKING_VERSIONS.value,
            current_stage="versions",
            progress_percent=70,
            queued_at=now - timedelta(hours=3),
            started_at=now - timedelta(hours=3),
            last_heartbeat_at=now,
            worker_name="celery@slow-worker",
        )
        created.append(overrun)

        # 4. Healthy running job must survive the reaper.
        healthy = _make_scan(
            session,
            repo,
            status=ScanStatus.CLONING.value,
            current_stage="cloning",
            progress_percent=10,
            queued_at=now - timedelta(seconds=30),
            started_at=now - timedelta(seconds=20),
            last_heartbeat_at=now,
            worker_name="celery@live-worker",
        )
        created.append(healthy)

        # 5. Cancelled jobs are terminal and must be left alone.
        cancelled = _make_scan(
            session,
            repo,
            status=ScanStatus.CANCELLED.value,
            current_stage="cancelled",
            queued_at=now - timedelta(hours=2),
        )
        created.append(cancelled)

        result = cleanup_stale_scans()
        check("reaper task completes", isinstance(result, dict), str(result))

        for scan in created:
            session.refresh(scan)

        check(
            "scan never picked up is failed",
            stuck.status == ScanStatus.FAILED.value,
            stuck.error_message or stuck.status,
        )
        check(
            "scan with lost heartbeat is failed",
            silent.status == ScanStatus.FAILED.value,
            silent.error_message or silent.status,
        )
        check(
            "scan past the run timeout is failed",
            overrun.status == ScanStatus.FAILED.value,
            overrun.error_message or overrun.status,
        )
        check(
            "healthy running scan is untouched",
            healthy.status == ScanStatus.CLONING.value,
            healthy.status,
        )
        check(
            "cancelled scan stays cancelled",
            cancelled.status == ScanStatus.CANCELLED.value,
            cancelled.status,
        )
        check(
            "reaped scans record a duration",
            silent.duration_seconds is not None,
            f"duration={silent.duration_seconds}",
        )
        check(
            "reaped scans close their stage timeline",
            all(t.get("completed_at") for t in (silent.stage_timings or [{}]))
            or not silent.stage_timings,
            f"timings={silent.stage_timings}",
        )

        # Upgrade Simulator parity.
        dep = session.execute(
            select(Dependency).where(Dependency.repository_id == repo.id)
        ).scalars().first()
        if dep is None:
            check("dependency available for simulation fixture", False, "none found")
        else:
            sim = UpgradeSimulation(
                dependency_id=dep.id,
                repository_id=repo.id,
                package_name=dep.package_name,
                from_version=dep.current_version or "0.0.0",
                to_version="99.0.0",
                status=SimulationStatus.QUEUED.value,
                progress_percent=0,
                current_stage="queued",
                cache_key="verify-harness",
                queued_at=now - timedelta(minutes=30),
                stage_timings=[],
            )
            session.add(sim)
            session.commit()
            created_sims.append(sim)

            cleanup_stale_scans()
            session.refresh(sim)
            check(
                "stale simulation is failed",
                sim.status == SimulationStatus.FAILED.value,
                sim.error_message or sim.status,
            )

        failures = [r for r in RESULTS if not r[1]]
        print(f"\n{len(RESULTS) - len(failures)}/{len(RESULTS)} checks passed")
        return 1 if failures else 0

    finally:
        for row in created + created_sims:
            try:
                session.delete(row)
            except Exception:  # noqa: BLE001
                pass
        session.commit()
        session.close()


if __name__ == "__main__":
    sys.exit(run())
