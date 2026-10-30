"""Celery workers — self-learning migration rules for any Python package."""

from __future__ import annotations

from typing import Any, Optional

from packaging.version import InvalidVersion, Version
from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import SyncSessionLocal
from app.core.logging import get_logger
from app.migration_engine.engine import MigrationEngine
from app.migration_engine.rule_store import RuleStore
from app.models.dependency import Dependency
from app.scanners.normalize import normalize_package_name

logger = get_logger(__name__)


def _safe_version(value: Optional[str]) -> Optional[Version]:
    if not value:
        return None
    try:
        return Version(str(value).lstrip("v"))
    except InvalidVersion:
        return None


@celery_app.task(
    bind=True,
    name="app.services.tasks.migration_engine_tasks.learn_library_rules",
    max_retries=2,
    soft_time_limit=600,
    time_limit=720,
)
def learn_library_rules(
    self,
    package_name: str,
    from_version: str,
    to_version: str,
    github_url: Optional[str] = None,
    force_refresh: bool = False,
    allow_ai: bool = False,
) -> dict[str, Any]:
    """
    Background learner:
    Fetch docs/releases → extract MigrationRules → validate → store permanently.
    Never regenerates existing rules unless force_refresh=True.

    ``allow_ai`` defaults False so Repository Scan self-learning stays deterministic
    and never burns LLM quota on Evaluation/Starter.
    """
    session = SyncSessionLocal()
    try:
        engine = MigrationEngine(session, allow_ai=allow_ai)
        rules = engine.ensure_rules(
            package_name,
            from_version,
            to_version,
            github_url=github_url,
            force_refresh=force_refresh,
        )
        session.commit()
        logger.info(
            "learn_library_rules_done",
            package=normalize_package_name(package_name),
            count=len(rules),
            range=f"{from_version}->{to_version}",
        )
        return {
            "package_name": package_name,
            "from_version": from_version,
            "to_version": to_version,
            "rules_count": len(rules),
            "status": "ok",
        }
    except Exception as exc:
        session.rollback()
        logger.exception("learn_library_rules_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60) from exc
    finally:
        session.close()


@celery_app.task(
    name="app.services.tasks.migration_engine_tasks.learn_rules_for_new_releases",
    soft_time_limit=900,
    time_limit=1200,
)
def learn_rules_for_new_releases(limit: int = 40) -> dict[str, Any]:
    """
    When new package versions appear on watched dependencies,
    automatically learn migration rules for installed→latest ranges.
    """
    session = SyncSessionLocal()
    queued = 0
    skipped = 0
    try:
        deps = (
            session.execute(
                select(Dependency)
                .where(Dependency.latest_version.is_not(None))
                .order_by(Dependency.updated_at.desc())
                .limit(limit * 3)
            )
            .scalars()
            .all()
        )
        store = RuleStore(session)
        seen: set[tuple[str, str, str]] = set()

        for dep in deps:
            from_v = dep.current_version
            to_v = dep.latest_version
            if not from_v or not to_v:
                skipped += 1
                continue
            lo = _safe_version(from_v)
            hi = _safe_version(to_v)
            if lo and hi and lo >= hi:
                skipped += 1
                continue

            key = (normalize_package_name(dep.package_name), from_v, to_v)
            if key in seen:
                skipped += 1
                continue
            seen.add(key)

            if store.has_rules(dep.package_name, from_v, to_v):
                skipped += 1
                continue

            learn_library_rules.delay(
                dep.package_name,
                from_v,
                to_v,
                dep.github_repo_url,
                False,
            )
            queued += 1
            if queued >= limit:
                break

        return {"queued": queued, "skipped": skipped}
    finally:
        session.close()
