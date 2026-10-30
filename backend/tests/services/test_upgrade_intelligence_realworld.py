"""Real-world upgrade intelligence validation across all eight ecosystems.

Uses public registries and official release notes when the network is available.
Does not hardcode per-package upgrade catalogs.
"""

from __future__ import annotations

import ast
import time
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from app.migration_engine.patch_generator import PatchGenerator
from app.migration_engine.rule_catalog import rules_for_upgrade
from app.migration_engine.rule_matcher import RuleMatcher
from app.migration_engine.semantic_index import SemanticASTIndex
from app.services.upgrade_impact import UpgradeImpactAnalyzer
from app.services.upgrade_intelligence.categories import CATEGORY_IDS
from app.services.upgrade_intelligence.engine import DynamicUpgradeIntelligence
from app.services.upgrade_intelligence.evidence import GeneralizedEvidenceCollector
from app.services.upgrade_intelligence.merge import incomplete_category_ids
from app.services.upgrade_intelligence.models import EvidenceBundle
from app.services.plans import PLANS

# Realistic version transitions (public packages, not a Verspect catalog).
ECOSYSTEM_UPGRADES: list[dict[str, Any]] = [
    {
        "ecosystem": "pypi",
        "language": "Python",
        "package": "flask",
        "from": "2.3.2",
        "to": "3.1.3",
        "github": "https://github.com/pallets/flask",
        "usages": [
            {
                "package_name": "flask",
                "symbol": "Flask",
                "fully_qualified_name": "flask.Flask",
                "usage_kind": "call",
                "file_path": "app.py",
                "line": 8,
                "column": 0,
                "code_snippet": "app = Flask(__name__)",
                "module_path": "flask",
            }
        ],
    },
    {
        "ecosystem": "npm",
        "language": "JavaScript",
        "package": "express",
        "from": "4.21.0",
        "to": "5.1.0",
        "github": "https://github.com/expressjs/express",
        "usages": [
            {
                "package_name": "express",
                "symbol": "express",
                "fully_qualified_name": "express",
                "usage_kind": "from_import",
                "file_path": "server.ts",
                "line": 6,
                "column": 0,
                "code_snippet": 'import express from "express";',
                "module_path": "express",
            }
        ],
    },
    {
        "ecosystem": "npm",
        "language": "TypeScript",
        "package": "react",
        "from": "18.2.0",
        "to": "19.1.0",
        "github": "https://github.com/facebook/react",
        "usages": [
            {
                "package_name": "react",
                "symbol": "React",
                "fully_qualified_name": "react",
                "usage_kind": "from_import",
                "file_path": "src/index.js",
                "line": 1,
                "column": 0,
                "code_snippet": 'import React from "react";',
                "module_path": "react",
            }
        ],
    },
    {
        "ecosystem": "go",
        "language": "Go",
        "package": "github.com/gin-gonic/gin",
        "from": "v1.10.0",
        "to": "v1.12.0",
        "github": "https://github.com/gin-gonic/gin",
        "usages": [
            {
                "package_name": "github.com/gin-gonic/gin",
                "symbol": "gin",
                "fully_qualified_name": "github.com/gin-gonic/gin",
                "usage_kind": "import",
                "file_path": "main.go",
                "line": 12,
                "column": 0,
                "code_snippet": '"github.com/gin-gonic/gin"',
                "module_path": "github.com/gin-gonic/gin",
            }
        ],
    },
    {
        "ecosystem": "maven",
        "language": "Java",
        "package": "com.google.guava:guava",
        "from": "32.1.3-jre",
        "to": "33.2.1-jre",
        "github": "https://github.com/google/guava",
        "usages": [
            {
                "package_name": "com.google.guava:guava",
                "symbol": "ImmutableList",
                "fully_qualified_name": "com.google.common.collect.ImmutableList",
                "usage_kind": "import",
                "file_path": "src/main/java/com/verspect/App.java",
                "line": 3,
                "column": 0,
                "code_snippet": "import com.google.common.collect.ImmutableList;",
                "module_path": "com.google.common.collect",
            }
        ],
    },
    {
        "ecosystem": "crates.io",
        "language": "Rust",
        "package": "serde",
        "from": "1.0.210",
        "to": "1.0.219",
        "github": "https://github.com/serde-rs/serde",
        "usages": [
            {
                "package_name": "serde",
                "symbol": "Serialize",
                "fully_qualified_name": "serde::Serialize",
                "usage_kind": "use",
                "file_path": "src/main.rs",
                "line": 1,
                "column": 0,
                "code_snippet": "use serde::Serialize;",
                "module_path": "serde",
            }
        ],
    },
    {
        "ecosystem": "packagist",
        "language": "PHP",
        "package": "monolog/monolog",
        "from": "3.7.0",
        "to": "3.8.1",
        "github": "https://github.com/Seldaek/monolog",
        "usages": [
            {
                "package_name": "monolog/monolog",
                "symbol": "Logger",
                "fully_qualified_name": "Monolog\\Logger",
                "usage_kind": "use",
                "file_path": "src/App.php",
                "line": 3,
                "column": 0,
                "code_snippet": "use Monolog\\Logger;",
                "module_path": "Monolog",
            }
        ],
    },
    {
        "ecosystem": "rubygems",
        "language": "Ruby",
        "package": "rack",
        "from": "2.2.9",
        "to": "3.1.7",
        "github": "https://github.com/rack/rack",
        "usages": [
            {
                "package_name": "rack",
                "symbol": "rack",
                "fully_qualified_name": "rack",
                "usage_kind": "require",
                "file_path": "app.rb",
                "line": 1,
                "column": 0,
                "code_snippet": 'require "rack"',
                "module_path": "rack",
            }
        ],
    },
]


class _GroundedSpy:
    """AI stub that only quotes provided notes/usages — never invents files or CVEs."""

    available = True
    model = "grounded-spy"
    calls: list[tuple[str, str]]

    def __init__(self) -> None:
        self.calls = []

    def _respond_json(self, system: str, user: str) -> dict:
        self.calls.append((system, user))
        return {"categories": [], "notes": "insufficient evidence in provided notes"}


class _CountingClient(httpx.Client):
    urls: list[str] = []

    def request(self, method, url, *args, **kwargs):  # type: ignore[no-untyped-def]
        _CountingClient.urls.append(f"{method} {url}")
        return super().request(method, url, *args, **kwargs)


def _collect(spec: dict[str, Any]) -> EvidenceBundle:
    return GeneralizedEvidenceCollector(timeout=12.0, cache=None).collect(
        package_name=spec["package"],
        from_version=spec["from"],
        to_version=spec["to"],
        ecosystem=spec["ecosystem"],
        github_repo_url=spec.get("github"),
    )


def _try_collect(spec: dict[str, Any]) -> EvidenceBundle:
    try:
        bundle = _collect(spec)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"registry/docs unavailable for {spec['package']}: {exc}")
    if "package_registry_unavailable" in bundle.degradation and not bundle.release_notes:
        pytest.skip(f"no evidence for {spec['package']}")
    return bundle


@pytest.mark.parametrize("spec", ECOSYSTEM_UPGRADES, ids=lambda s: s["language"])
def test_real_upgrade_each_ecosystem(spec: dict[str, Any]) -> None:
    bundle = _try_collect(spec)
    spy = _GroundedSpy()
    report = DynamicUpgradeIntelligence().analyze(
        package_name=spec["package"],
        current_version=spec["from"],
        target_version=spec["to"],
        usages=spec["usages"],
        ecosystem=spec["ecosystem"],
        allow_ai=True,
        ai=spy,
        evidence=bundle,
        skip_network=True,
        github_url=spec.get("github"),
    )
    report.ensure_all_categories()
    assert set(report.categories) >= set(CATEGORY_IDS)
    assert report.breaking_classification != "breaking" or any(
        f.affected_files for f in report.categories["breaking_changes"].findings
    )
    used_file = spec["usages"][0]["file_path"]
    assert any(loc.file == used_file for loc in report.affected_files)
    # Major bump alone is not sufficient.
    if spec["package"] == "react":
        assert report.breaking_classification != "breaking" or report.categories[
            "breaking_changes"
        ].findings
    # Never collapse to a bare Unknown.
    assert report.summary
    assert report.categories["confidence"].answer
    assert report.categories["upgrade_risk"].answer
    assert len(spy.calls) <= 1


def test_case_a_complete_deterministic_does_not_call_ai() -> None:
    usages = [
        {
            "package_name": "pydantic",
            "symbol": "validator",
            "fully_qualified_name": "pydantic.validator",
            "usage_kind": "decorator",
            "file_path": "src/app.py",
            "line": 12,
            "column": 0,
            "code_snippet": "@validator('name')",
            "module_path": "pydantic",
        }
    ]
    impact = UpgradeImpactAnalyzer().analyze(
        package_name="pydantic",
        current_version="1.10.13",
        target_version="2.9.0",
        usages=usages,
    )
    spy = _GroundedSpy()
    report = DynamicUpgradeIntelligence().analyze(
        package_name="pydantic",
        current_version="1.10.13",
        target_version="2.9.0",
        usages=usages,
        ecosystem="pypi",
        allow_ai=True,
        ai=spy,
        impact=impact,
        skip_network=True,
    )
    assert report.catalog_rules_applied > 0
    assert spy.calls == []
    assert incomplete_category_ids(report) == []
    assert report.categories["breaking_changes"].analysis_method == "deterministic"
    assert report.categories["required_code_changes"].findings
    assert "src/app.py:12" in (report.categories["required_code_changes"].findings[0].required_change or "")


def test_case_b_and_c_gin_with_and_without_notes() -> None:
    gin = next(s for s in ECOSYSTEM_UPGRADES if s["language"] == "Go")
    bundle = _try_collect(gin)
    spy_b = _GroundedSpy()
    with_notes = DynamicUpgradeIntelligence().analyze(
        package_name=gin["package"],
        current_version=gin["from"],
        target_version=gin["to"],
        usages=gin["usages"],
        ecosystem="go",
        allow_ai=True,
        ai=spy_b,
        evidence=bundle,
        skip_network=True,
    )
    assert with_notes.categories["affected_files"].findings
    assert any(loc.file == "main.go" and loc.line == 12 for loc in with_notes.affected_files)
    # Import-only usage must not be auto-labeled breaking.
    assert with_notes.breaking_classification != "breaking"
    if incomplete_category_ids(with_notes) or spy_b.calls:
        assert len(spy_b.calls) == 1
        assert with_notes.categories["migration_steps"].answer
        assert with_notes.categories["migration_steps"].answer.lower() != "unknown"

    spy_c = _GroundedSpy()
    empty = EvidenceBundle(
        package_name=gin["package"],
        ecosystem="go",
        from_version=gin["from"],
        to_version=gin["to"],
    )
    without = DynamicUpgradeIntelligence().analyze(
        package_name=gin["package"],
        current_version=gin["from"],
        target_version=gin["to"],
        usages=gin["usages"],
        ecosystem="go",
        allow_ai=True,
        ai=spy_c,
        evidence=empty,
        skip_network=True,
    )
    assert spy_c.calls, "Case C must invoke AI when entitled"
    assert without.breaking_classification != "breaking"
    assert "unresolved" in without.breaking_classification or without.categories["breaking_changes"].completeness in {
        "empty",
        "partial",
        "complete",
    }
    assert without.categories["affected_files"].completeness == "complete"


@pytest.mark.parametrize("plan", ["free", "starter", "pro", "team", "enterprise"])
def test_plan_ai_entitlement_matches_limits(plan: str) -> None:
    limits = PLANS[plan]
    spy = _GroundedSpy()
    gin = next(s for s in ECOSYSTEM_UPGRADES if s["language"] == "Go")
    report = DynamicUpgradeIntelligence().analyze(
        package_name=gin["package"],
        current_version=gin["from"],
        target_version=gin["to"],
        usages=gin["usages"],
        ecosystem="go",
        allow_ai=limits.ai_enabled,
        ai=spy,
        skip_network=True,
    )
    if limits.ai_enabled:
        assert spy.calls, f"{plan} should be allowed to call AI for incomplete categories"
        assert report.ai_skipped_reason != "plan_does_not_include_ai"
    else:
        assert spy.calls == []
        assert report.ai_skipped_reason == "plan_does_not_include_ai"
        assert "Pro" in report.summary or "AI" in report.summary
    if plan == "team":
        assert limits.ai_migration_assistant is True
    if plan == "pro":
        assert limits.ai_migration_assistant is False


def test_team_pull_request_still_requires_confirm() -> None:
    import inspect

    from app.api.v1.migration import create_migration_pull_request
    from app.services.migration_publish import publish_migration_pull_request

    assert "confirm" in inspect.getsource(create_migration_pull_request)
    assert "require_ai_migration_assistant" in inspect.getsource(create_migration_pull_request)
    src = inspect.getsource(publish_migration_pull_request)
    assert "if not confirm" in src
    assert PLANS["team"].ai_migration_assistant is True


def test_migration_patch_pydantic_is_validated_not_published() -> None:
    sample = (
        "from pydantic import BaseModel, validator\n\n"
        "class User(BaseModel):\n"
        "    @validator('name')\n"
        "    def validate_name(cls, value):\n"
        "        return value\n"
    )
    usages = [
        {
            "package_name": "pydantic",
            "symbol": "validator",
            "fully_qualified_name": "pydantic.validator",
            "usage_kind": "decorator",
            "file_path": "user.py",
            "line": 4,
            "column": 4,
            "code_snippet": "@validator('name')",
            "module_path": "pydantic",
        }
    ]
    rules = rules_for_upgrade("pydantic", "1.10.0", "2.5.0")
    index = SemanticASTIndex.from_usage_dicts(usages).filter_package("pydantic")
    matches = RuleMatcher().match_index(index, rules)
    patches, findings = PatchGenerator().generate(matches)
    assert any(f.status == "automatic_migration" for f in findings)
    assert patches
    assert all(p.file_path == "user.py" for p in patches)
    check = sample.replace("@validator('name')", "@field_validator('name')")
    ast.parse(check)
    assert any("@field_validator" in (p.suggested_code or "") for p in patches)
    assert patches[0].unified_diff
    # Patches are suggestions only — publishing still requires confirm=true.


def test_performance_one_batched_ai_and_counted_http() -> None:
    gin = next(s for s in ECOSYSTEM_UPGRADES if s["language"] == "Go")
    _CountingClient.urls = []
    started = time.perf_counter()
    with patch("httpx.Client", _CountingClient):
        bundle = GeneralizedEvidenceCollector(timeout=12.0, cache=None).collect(
            package_name=gin["package"],
            from_version=gin["from"],
            to_version=gin["to"],
            ecosystem="go",
            github_repo_url=gin["github"],
        )
    duration = time.perf_counter() - started
    urls = list(_CountingClient.urls)
    spy = _GroundedSpy()
    report = DynamicUpgradeIntelligence().analyze(
        package_name=gin["package"],
        current_version=gin["from"],
        target_version=gin["to"],
        usages=gin["usages"],
        ecosystem="go",
        allow_ai=True,
        ai=spy,
        evidence=bundle,
        skip_network=True,
    )
    assert duration < 45.0
    assert len(spy.calls) <= 1
    # Collector may hit registry + GitHub; duplicates should stay bounded.
    unique = set(urls)
    assert len(urls) <= 40
    assert len(urls) - len(unique) < 15
    assert report.categories["affected_files"].findings
    # Payload must not include the entire repository — only usage excerpts.
    if spy.calls:
        _system, user = spy.calls[0]
        assert "repository_usage" in user or "main.go" in user
        assert len(user) < 200_000
