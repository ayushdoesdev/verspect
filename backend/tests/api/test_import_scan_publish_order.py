"""Repository Import must not publish Celery tasks before Scan rows commit."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.api.v1.repositories import _publish_committed_import_scans


@pytest.mark.asyncio
async def test_publish_committed_import_scans_sets_task_id_and_commits():
    scan_id = uuid4()
    scan = MagicMock()
    scan.id = scan_id
    scan.celery_task_id = None

    db = AsyncMock()
    db.get = AsyncMock(return_value=scan)
    db.commit = AsyncMock()

    task = MagicMock()
    task.id = "celery-task-abc"

    with patch(
        "app.services.tasks.scan_tasks.run_repository_scan"
    ) as run_scan:
        run_scan.delay.return_value = task
        await _publish_committed_import_scans(db, [scan_id])

    run_scan.delay.assert_called_once_with(str(scan_id))
    assert scan.celery_task_id == "celery-task-abc"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_publish_committed_import_scans_noop_for_empty_list():
    db = AsyncMock()
    with patch(
        "app.services.tasks.scan_tasks.run_repository_scan"
    ) as run_scan:
        await _publish_committed_import_scans(db, [])
    run_scan.delay.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_commits_before_celery_publish():
    """Ordering invariant: durable commit, then delay(), then task-id commit."""
    from app.models.scan import Scan

    events: list[str] = []
    scan_id = uuid4()
    scan = MagicMock()
    scan.id = scan_id
    scan.celery_task_id = None

    class TrackingSession:
        async def get(self, model, pk):  # noqa: ANN001
            assert model is Scan
            assert pk == scan_id
            events.append("db.get")
            return scan

        async def commit(self) -> None:
            events.append("commit")

    db = TrackingSession()

    def fake_delay(sid: str):
        events.append(f"delay:{sid}")
        task = MagicMock()
        task.id = "t-1"
        return task

    with patch(
        "app.services.tasks.scan_tasks.run_repository_scan"
    ) as run_scan:
        run_scan.delay.side_effect = fake_delay
        # Mimic import_repositories: commit first, then publish.
        await db.commit()
        events.append("after_scan_commit")
        await _publish_committed_import_scans(db, [scan_id])  # type: ignore[arg-type]

    assert events == [
        "commit",
        "after_scan_commit",
        "db.get",
        f"delay:{scan_id}",
        "commit",
    ]
    assert scan.celery_task_id == "t-1"