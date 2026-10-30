"""Regression: catalog rules with shared (symbol, kind) and distinct match_kind."""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select, text

from app.core.database import SyncSessionLocal
from app.migration_engine.engine import MigrationEngine
from app.migration_engine.rule_catalog import rules_for_upgrade
from app.models.knowledge import MigrationRule


@pytest.fixture
def db_session():
    session = SyncSessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        session.close()


def _cleanup_pydantic_range(session) -> None:
    session.execute(
        delete(MigrationRule).where(
            MigrationRule.normalized_name == "pydantic",
            MigrationRule.from_version == "1.10.13",
            MigrationRule.to_version == "2.13.4",
        )
    )
    session.commit()


def test_catalog_has_distinct_basemodel_match_kinds():
    catalog = rules_for_upgrade("pydantic", "1.10.13", "2.13.4")
    base = [r for r in catalog if r.symbol == "BaseModel"]
    assert len(base) == 2
    assert {r.match_kind for r in base} == {"import", "inheritance"}
    # Identity must include match_kind — otherwise these collide.
    keys = {(r.symbol, r.kind, r.match_kind or "") for r in catalog}
    assert len(keys) == len(catalog)


def test_pydantic_catalog_persists_basemodel_match_kinds(db_session):
    _cleanup_pydantic_range(db_session)

    engine = MigrationEngine(db_session, ai=None)
    rules = engine.ensure_rules("pydantic", "1.10.13", "2.13.4", force_refresh=False)
    assert len(rules) >= 8

    # Outer session must remain usable (no PendingRollbackError)
    db_session.flush()
    db_session.commit()

    rows = (
        db_session.execute(
            select(MigrationRule).where(
                MigrationRule.normalized_name == "pydantic",
                MigrationRule.from_version == "1.10.13",
                MigrationRule.to_version == "2.13.4",
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) >= 8
    base = [r for r in rows if r.symbol == "BaseModel" and r.kind == "behavior_change"]
    assert len(base) == 2
    assert {r.match_kind for r in base} == {"import", "inheritance"}

    # Idempotent second pass
    engine.ensure_rules("pydantic", "1.10.13", "2.13.4", force_refresh=False)
    db_session.commit()
    count = db_session.execute(
        select(MigrationRule).where(
            MigrationRule.normalized_name == "pydantic",
            MigrationRule.from_version == "1.10.13",
            MigrationRule.to_version == "2.13.4",
        )
    ).scalars().all()
    assert len(count) == len(rows)

    _cleanup_pydantic_range(db_session)


def test_match_kind_column_in_unique_constraint(db_session):
    row = db_session.execute(
        text(
            """
            SELECT pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            WHERE t.relname = 'migration_rules'
              AND c.conname = 'uq_migration_rules_identity'
            """
        )
    ).scalar()
    assert row is not None
    assert "match_kind" in row
