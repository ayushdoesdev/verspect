"""KnowledgeBaseEntry must behave like a concurrent-safe cache."""

from __future__ import annotations

import threading
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from app.core.database import SyncSessionLocal
from app.migration_engine.rule_store import RuleStore
from app.models.knowledge import KnowledgeBaseEntry
from app.scanners.normalize import normalize_package_name


PKG = f"numpy-kb-test-{uuid4().hex[:8]}"
NORMALIZED = normalize_package_name(PKG)


@pytest.fixture
def db_session():
    session = SyncSessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        session.close()


def _cleanup(session) -> None:
    session.execute(
        delete(KnowledgeBaseEntry).where(
            KnowledgeBaseEntry.normalized_name == NORMALIZED,
            KnowledgeBaseEntry.ecosystem == "PyPI",
        )
    )
    session.commit()


def test_get_or_create_kb_reuses_existing_row(db_session):
    _cleanup(db_session)
    store = RuleStore(db_session)

    first = store.get_or_create_kb(PKG, github_url="https://github.com/numpy/numpy")
    db_session.commit()

    second = store.get_or_create_kb(PKG, pypi_url=f"https://pypi.org/project/{NORMALIZED}/")
    db_session.commit()

    assert first.id == second.id
    assert second.github_url == "https://github.com/numpy/numpy"

    count = db_session.execute(
        select(func.count())
        .select_from(KnowledgeBaseEntry)
        .where(
            KnowledgeBaseEntry.normalized_name == NORMALIZED,
            KnowledgeBaseEntry.ecosystem == "PyPI",
        )
    ).scalar_one()
    assert count == 1
    _cleanup(db_session)


def test_get_or_create_kb_concurrent_inserts_single_row():
    """Two sessions racing INSERT must reuse one row — no UniqueViolation."""
    setup = SyncSessionLocal()
    try:
        _cleanup(setup)
    finally:
        setup.close()

    errors: list[BaseException] = []
    ids: list = []
    barrier = threading.Barrier(2)

    def worker() -> None:
        session = SyncSessionLocal()
        try:
            store = RuleStore(session)
            barrier.wait(timeout=10)
            entry = store.get_or_create_kb(
                PKG,
                pypi_url=f"https://pypi.org/project/{NORMALIZED}/",
                github_url="https://github.com/numpy/numpy",
            )
            session.commit()
            ids.append(entry.id)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
            session.rollback()
        finally:
            session.close()

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)

    assert errors == [], f"concurrent KB create failed: {errors}"
    assert len(ids) == 2
    assert ids[0] == ids[1]

    verify = SyncSessionLocal()
    try:
        count = verify.execute(
            select(func.count())
            .select_from(KnowledgeBaseEntry)
            .where(
                KnowledgeBaseEntry.normalized_name == NORMALIZED,
                KnowledgeBaseEntry.ecosystem == "PyPI",
            )
        ).scalar_one()
        assert count == 1
        _cleanup(verify)
    finally:
        verify.close()


def test_sanitize_engine_error_hides_unique_violation():
    from app.services.upgrade_helpers import sanitize_engine_error

    class UniqueViolation(Exception):
        pass

    msg = sanitize_engine_error(
        UniqueViolation(
            'duplicate key value violates unique constraint "uq_kb_normalized_eco"'
        )
    )
    assert "uq_kb_normalized_eco" not in msg
    assert "duplicate key" not in msg.lower()
    assert "concurrently" in msg.lower() or "deterministic" in msg.lower()
