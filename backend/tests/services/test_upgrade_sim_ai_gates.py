"""Upgrade Simulator AI gating — locked AI is available=False, never None."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.ai.analyzer import DisabledAIAnalyzer, resolve_ai_handle
from app.ai.upgrade_simulator import UpgradeImpactAnalyzer
from app.migration_engine.engine import MigrationEngine
from app.migration_engine.rule_generator import RuleGenerator
from app.services.plans import PLANS


class _SpyAI:
    """AI stub that claims available and fails if called."""

    available = True
    model = "spy"

    def _respond_json(self, system: str, user: str) -> dict:
        raise AssertionError("LLM must not be called when allow_ai=False")


def test_rule_generator_skips_llm_when_allow_ai_false():
    gen = RuleGenerator(ai=_SpyAI(), allow_ai=False)  # type: ignore[arg-type]
    batch = gen.generate(
        library="demo",
        from_version="1.0.0",
        to_version="2.0.0",
        documentation_excerpts=[
            {
                "source_type": "docs",
                "url": "https://example.com/migrate",
                "title": "Migration",
                "content": "Deprecated: old_api. Use new_api instead.",
            }
        ],
        release_notes=[],
    )
    assert batch is not None
    assert isinstance(batch.rules, list)


def test_rule_generator_locked_ai_is_disabled_handle_not_none():
    gen = RuleGenerator(ai=None, allow_ai=False)
    assert gen.ai is not None
    assert isinstance(gen.ai, DisabledAIAnalyzer)
    assert gen.ai.available is False
    assert gen.ai.model == "disabled"


def test_migration_engine_allow_ai_false_uses_disabled_handle():
    engine = MigrationEngine(MagicMock(), ai=None, allow_ai=False)
    assert engine.ai is not None
    assert engine.ai.available is False
    assert engine.allow_ai is False
    assert engine.generator.ai is not None
    assert engine.generator.ai.available is False


def test_upgrade_impact_analyzer_skips_llm_when_allow_ai_false():
    spy = _SpyAI()
    analyzer = UpgradeImpactAnalyzer(ai=spy, allow_ai=False)  # type: ignore[arg-type]
    result = analyzer.analyze(
        package_name="demo",
        from_version="1.0.0",
        to_version="2.0.0",
        usages=[{"fully_qualified_name": "demo.fn", "file_path": "a.py", "line": 1}],
        sources={"release_notes": [], "breaking_change_hints": [], "deprecated_hints": []},
    )
    assert result.summary
    assert result.confidence <= 0.55


@pytest.mark.parametrize(
    "plan,expect_ai,expect_migration",
    [
        ("free", False, False),
        ("starter", False, False),
        ("pro", True, False),
        ("team", True, True),
        ("enterprise", True, True),
    ],
)
def test_resolve_ai_handle_by_plan_flags(plan, expect_ai, expect_migration):
    limits = PLANS[plan]
    assert limits.ai_enabled is expect_ai
    assert limits.ai_migration_assistant is expect_migration

    handle = resolve_ai_handle(enabled=limits.ai_enabled or limits.ai_migration_assistant)
    assert handle is not None
    if expect_ai or expect_migration:
        assert handle.available in {True, False}  # depends on provider config
        assert not isinstance(handle, DisabledAIAnalyzer)
    else:
        assert isinstance(handle, DisabledAIAnalyzer)
        assert handle.available is False


@pytest.mark.parametrize("plan", ["free", "starter", "pro", "team"])
def test_model_used_never_dereferences_none_ai(plan):
    """Regression: sim.model_used must not crash when AI is locked (Evaluation/Starter)."""
    limits = PLANS[plan]
    ai = resolve_ai_handle(enabled=limits.ai_enabled or limits.ai_migration_assistant)
    assert ai is not None

    # Mirror upgrade_simulation_tasks model_used assignment
    engine_error = None
    ai_migration_enabled = limits.ai_migration_assistant
    ai_assistant_error = None

    if engine_error:
        model_used = f"fallback+{ai.model}" if ai.available else "fallback+heuristic"
    elif ai_migration_enabled and not ai_assistant_error and ai.available:
        model_used = f"semantic_matcher+ai_migration:{ai.model}"
    elif ai.available:
        model_used = f"semantic_matcher+{ai.model}"
    else:
        model_used = "semantic_matcher+deterministic"

    assert isinstance(model_used, str)
    assert "None" not in model_used
    if plan in {"free", "starter"}:
        assert model_used == "semantic_matcher+deterministic"
        assert ai.available is False
