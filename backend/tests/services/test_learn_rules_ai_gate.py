"""Regression H5: scan self-learning must not enable LLMs by default."""

from __future__ import annotations

import inspect

from app.services.tasks import migration_engine_tasks as tasks


def test_learn_library_rules_defaults_allow_ai_false() -> None:
    sig = inspect.signature(tasks.learn_library_rules)
    assert sig.parameters["allow_ai"].default is False


def test_learn_library_rules_passes_allow_ai_into_engine() -> None:
    src = inspect.getsource(tasks.learn_library_rules)
    assert "MigrationEngine(session, allow_ai=allow_ai)" in src
    assert "AIAnalyzer()" not in src


def test_ai_chat_requires_ai_entitlement() -> None:
    from app.api.v1 import ai as ai_api

    src = inspect.getsource(ai_api.ai_chat)
    assert "require_ai_feature" in src


def test_learn_rules_sync_requires_ai_entitlement() -> None:
    from app.api.v1 import migration as migration_api

    src = inspect.getsource(migration_api.learn_rules_sync)
    assert "require_ai_feature" in src


def test_simulation_cancel_does_not_expire_all() -> None:
    from app.services.tasks.upgrade_simulation_tasks import _is_simulation_cancelled

    src = inspect.getsource(_is_simulation_cancelled)
    assert "session.expire_all(" not in src
    assert "session.refresh" in src
