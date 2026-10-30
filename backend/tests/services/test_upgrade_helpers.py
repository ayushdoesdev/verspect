"""Tests for AST-first upgrade helpers (RC regression fix)."""

from app.services.upgrade_helpers import (
    build_ast_affected_files,
    build_upgrade_advisor,
    collect_official_references,
    confidence_label,
)


def test_ast_affected_files_includes_all_usages():
    usages = [
        {
            "fully_qualified_name": "pkg.a.Foo",
            "symbol": "Foo",
            "usage_kind": "import",
            "file_path": "src/a.py",
            "line": 1,
            "enclosing_function": None,
            "enclosing_class": None,
        },
        {
            "fully_qualified_name": "pkg.b.Bar",
            "symbol": "Bar",
            "usage_kind": "call",
            "file_path": "src/b.py",
            "line": 10,
            "enclosing_function": "run",
            "enclosing_class": None,
            "code_snippet": "Bar()",
        },
        {
            "fully_qualified_name": "pkg.a.Foo",
            "symbol": "Foo",
            "usage_kind": "call",
            "file_path": "src/a.py",
            "line": 20,
            "enclosing_function": "main",
            "enclosing_class": "App",
        },
    ]
    files = build_ast_affected_files(usages)
    assert len(files) == 2
    by_path = {f["file_path"]: f for f in files}
    assert "src/a.py" in by_path
    assert "src/b.py" in by_path
    assert len(by_path["src/a.py"]["usage_sites"]) == 2
    assert "pkg.a.Foo" in by_path["src/a.py"]["affected_apis"]
    assert by_path["src/a.py"]["enclosing_functions"] == ["main"]


def test_ast_files_merge_rule_annotations():
    usages = [
        {
            "fully_qualified_name": "pkg.Old",
            "symbol": "Old",
            "file_path": "x.py",
            "line": 3,
            "usage_kind": "import",
        }
    ]
    files = build_ast_affected_files(
        usages,
        rule_annotations={
            "x.py": [
                {
                    "symbol": "pkg.Old",
                    "kind": "removed",
                    "severity": "high",
                    "description": "removed in 2.0",
                    "confidence": 0.8,
                }
            ]
        },
    )
    assert files[0]["rules"]
    assert "migration-rule" in files[0]["reason"]


def test_official_refs_always_include_pypi():
    refs = collect_official_references(package_name="requests")
    assert any("pypi.org/project/requests" in r for r in refs)


def test_classify_identical_is_no_migration_or_manual_when_risk():
    from app.services.upgrade_helpers import (
        build_migration_finding,
        classify_migration_finding,
        code_differs,
    )

    assert not code_differs("x = 1", "x = 1")
    assert not code_differs("x = 1", "# Manual review required\nx = 1")
    assert code_differs("x = 1", "x = 2")

    assert (
        classify_migration_finding(
            current_code="x = 1",
            suggested_code="x = 1",
            automatic=False,
            confidence=0.4,
            risk_flagged=False,
        )
        == "no_migration_required"
    )
    assert (
        classify_migration_finding(
            current_code="x = 1",
            suggested_code="x = 1",
            automatic=False,
            confidence=0.4,
            risk_flagged=True,
        )
        == "manual_review_required"
    )
    assert (
        classify_migration_finding(
            current_code="old()",
            suggested_code="new()",
            automatic=True,
            confidence=0.9,
            validation_status="validated",
        )
        == "automatic_migration"
    )

    manual = build_migration_finding(
        file_path="a.py",
        line=1,
        symbol="pkg.x",
        current_code="pkg.x()",
        suggested_code="# Manual review required\npkg.x()",
        explanation="Review docs",
        confidence=0.4,
        automatic=False,
        official_reference="https://example.com",
        risk_flagged=True,
    )
    assert manual["migration_status"] == "manual_review_required"
    assert manual["suggested_code"] is None
    assert manual["unified_diff"] is None

    auto = build_migration_finding(
        file_path="a.py",
        line=1,
        symbol="pkg.x",
        current_code="old()",
        suggested_code="new()",
        explanation="renamed",
        confidence=0.9,
        automatic=True,
        validation_status="validated",
        unified_diff="--- a\n+++ b",
    )
    assert auto["migration_status"] == "automatic_migration"
    assert auto["suggested_code"] == "new()"


def test_upgrade_advisor_security_action():
    adv = build_upgrade_advisor(
        package_name="cryptography",
        current_version="41.0.0",
        latest_version="42.0.0",
        is_outdated=True,
        has_vulnerabilities=True,
        vulnerability_count=2,
        critical_vuln_count=1,
        major_behind=0,
        health_score=80,
        risk_score=40,
        ai_should_update=None,
        usage_count=12,
    )
    assert adv["immediate_action"] == "Upgrade now"
    assert adv["confidence_label"] in {"Low", "Medium", "High"}
    assert confidence_label(0.9) == "High"
