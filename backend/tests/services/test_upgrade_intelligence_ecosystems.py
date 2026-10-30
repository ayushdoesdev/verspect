"""Realistic upgrade fixtures across all eight supported ecosystems."""

from __future__ import annotations

from app.services.upgrade_intelligence.categories import CATEGORY_IDS
from app.services.upgrade_intelligence.engine import DynamicUpgradeIntelligence
from app.services.upgrade_intelligence.models import EvidenceBundle, EvidenceItem


def _usage(package: str, symbol: str, fqn: str, file_path: str, line: int, snippet: str = "") -> dict:
    return {
        "package_name": package,
        "symbol": symbol,
        "fully_qualified_name": fqn,
        "usage_kind": "call",
        "file_path": file_path,
        "line": line,
        "column": 1,
        "code_snippet": snippet or fqn,
        "module_path": package,
    }


def _extracted(kind: str, ident: str, line: str) -> dict:
    return {"kind": kind, "identifier": ident, "line": line, "source": "changelog", "all_kinds": [kind]}


def _bundle(package: str, eco: str, extracted: list[dict], notes: str) -> EvidenceBundle:
    return EvidenceBundle(
        package_name=package,
        ecosystem=eco,
        from_version="1.0.0",
        to_version="2.0.0",
        release_notes=[{"source": "changelog", "text": notes, "url": f"https://example.test/{package}"}],
        extracted_changes=extracted,
        items=[
            EvidenceItem(
                kind="release_notes",
                text=notes,
                source=f"https://example.test/{package}",
                reliability="medium",
            )
        ],
        documentation_urls=[{"type": "changelog", "url": f"https://example.test/{package}", "label": "Changelog"}],
    )


def _run(package: str, eco: str, usages: list[dict], extracted: list[dict], notes: str):
    return DynamicUpgradeIntelligence().analyze(
        package_name=package,
        current_version="1.0.0",
        target_version="2.0.0",
        usages=usages,
        ecosystem=eco,
        allow_ai=False,
        evidence=_bundle(package, eco, extracted, notes),
        skip_network=True,
    )


def _assert_core(report, file_path: str) -> None:
    report.ensure_all_categories()
    assert set(report.categories) >= set(CATEGORY_IDS)
    files = {loc.file for loc in report.affected_files}
    assert file_path in files
    assert report.categories["affected_files"].completeness == "complete"
    assert report.breaking_classification != "unresolved" or report.categories["breaking_changes"].gaps


def test_python_removed_api() -> None:
    report = _run(
        "requests",
        "pypi",
        [_usage("requests", "json", "Response.json", "client.py", 20, "resp.json()")],
        [_extracted("removed", "json", "removed `json` helper")],
        "## Breaking\n- removed `json`",
    )
    _assert_core(report, "client.py")
    assert report.categories["removed_apis"].findings
    assert "client.py:20" in (report.required_changes[0].required_change or "")


def test_javascript_renamed_api() -> None:
    report = _run(
        "express",
        "npm",
        [_usage("express", "del", "app.del", "server.js", 14, "app.del('/x', h)")],
        [_extracted("renamed", "del", "renamed `del` to `delete`")],
        "BREAKING: renamed `del` to `delete`",
    )
    _assert_core(report, "server.js")
    assert report.categories["renamed_apis"].findings
    assert report.breaking_classification in {"potentially_breaking", "breaking"}


def test_typescript_signature_change() -> None:
    report = _run(
        "zod",
        "npm",
        [_usage("zod", "parse", "z.parse", "schema.ts", 8, "z.parse(input)")],
        [_extracted("signature_change", "parse", "`parse` now returns branded types")],
        "- signature of `parse` changed",
    )
    _assert_core(report, "schema.ts")
    assert report.categories["changed_signatures"].findings


def test_go_removed_and_unchanged() -> None:
    report = _run(
        "github.com/gin-gonic/gin",
        "go",
        [
            _usage("github.com/gin-gonic/gin", "JSON", "gin.Context.JSON", "main.go", 12, "c.JSON(200, obj)"),
            _usage("github.com/gin-gonic/gin", "GET", "router.GET", "main.go", 8, "r.GET(\"/\", h)"),
        ],
        [
            _extracted("removed", "JSON", "removed `JSON`"),
            _extracted("behavior_change", "Unrelated", "changed Unrelated helper"),
        ],
        "BREAKING: removed `JSON`\n- Unrelated helper behavior change",
    )
    _assert_core(report, "main.go")
    removed = {f.finding for f in report.categories["removed_apis"].findings}
    assert "JSON" in removed
    # Unrelated identifier is not claimed as verified usage
    for f in report.categories["removed_apis"].findings:
        if f.finding == "Unrelated":
            assert not f.affected_files


def test_java_deprecated_api() -> None:
    report = _run(
        "com.google.guava:guava",
        "maven",
        [_usage("com.google.guava:guava", "Files", "Files.toString", "App.java", 40, "Files.toString(f)")],
        [_extracted("deprecated", "Files", "deprecated `Files.toString`")],
        "Deprecated: `Files.toString` — use Files.asCharSource",
    )
    _assert_core(report, "App.java")
    assert report.categories["deprecated_functionality"].findings


def test_rust_configuration_change() -> None:
    report = _run(
        "serde",
        "crates.io",
        [_usage("serde", "Deserialize", "serde::Deserialize", "src/lib.rs", 3, "#[derive(Deserialize)]")],
        [_extracted("configuration", "default", "default feature flags changed")],
        "Configuration: default features no longer include derive",
    )
    _assert_core(report, "src/lib.rs")
    assert report.categories["changed_configuration"].findings or report.categories["changed_defaults"].findings


def test_php_module_import_change() -> None:
    report = _run(
        "laravel/framework",
        "packagist",
        [_usage("laravel/framework", "Route", "Illuminate\\Support\\Facades\\Route", "routes/web.php", 6, "Route::get")],
        [_extracted("import_path_change", "Route", "import path for `Route` facade changed")],
        "Breaking: import path for `Route` changed",
    )
    _assert_core(report, "routes/web.php")
    assert report.categories["changed_modules"].findings


def test_ruby_behavioral_change_used() -> None:
    report = _run(
        "rails",
        "rubygems",
        [_usage("rails", "update_attributes", "ActiveRecord::Base.update_attributes", "app/models/user.rb", 22, "user.update_attributes!")],
        [_extracted("behavior_change", "update_attributes", "default of `update_attributes` now raises")],
        "Behavior change: `update_attributes` now raises on failure",
    )
    _assert_core(report, "app/models/user.rb")
    assert report.categories["changed_defaults"].findings
    assert report.breaking_classification in {"potentially_breaking", "breaking", "low_risk"}


def test_unchanged_api_does_not_force_breaking() -> None:
    report = _run(
        "lodash",
        "npm",
        [_usage("lodash", "map", "_.map", "util.ts", 5, "_.map(xs, fn)")],
        [_extracted("removed", "pluck", "removed `pluck`")],
        "removed `pluck` — use `map`",
    )
    _assert_core(report, "util.ts")
    # map is used; pluck is not
    for f in report.categories["removed_apis"].findings:
        if f.finding == "pluck":
            assert f.status in {"possible", "likely"}
            assert not f.affected_files
    assert report.breaking_classification in {"low_risk", "safe", "unresolved"}
    assert report.breaking_classification != "breaking"
    assert report.breaking_classification != "potentially_breaking"


def test_ai_fill_for_ecosystem_without_catalog() -> None:
    class _AI:
        available = True
        model = "test"
        calls = []

        def _respond_json(self, system, user):
            self.calls.append(user)
            return {
                "categories": [
                    {
                        "category": "migration_steps",
                        "answer": "Replace del with delete at server.js:14.",
                        "status": "likely",
                        "findings": [
                            {
                                "category": "migration_steps",
                                "finding": "del",
                                "explanation": "`server.js:14` uses del. Target release removes it. Replace with delete.",
                                "affected_files": [
                                    {"file": "server.js", "line": 14, "api": "app.del", "reason": "usage"}
                                ],
                                "required_change": "`server.js:14` uses del. Replace with delete.",
                                "confidence": 0.66,
                                "status": "likely",
                                "evidence": ["renamed del to delete"],
                            }
                        ],
                    }
                ]
            }

    ai = _AI()
    report = DynamicUpgradeIntelligence().analyze(
        package_name="express",
        current_version="4.18.2",
        target_version="5.0.0",
        usages=[_usage("express", "del", "app.del", "server.js", 14)],
        ecosystem="npm",
        allow_ai=True,
        ai=ai,
        evidence=_bundle(
            "express",
            "npm",
            [_extracted("removed", "configure", "removed `configure`")],
            "removed `configure` — unrelated to del",
        ),
        skip_network=True,
    )
    assert ai.calls
    steps = report.categories["migration_steps"]
    assert steps.analysis_method in {"ai", "deterministic+ai"}
    assert any("server.js:14" in (f.required_change or f.explanation) for f in steps.findings)
