"""Deterministic upgrade impact analysis tests."""

from __future__ import annotations

from app.migration_engine.rule_catalog import rules_for_upgrade, version_crosses
from app.services.upgrade_impact import UpgradeImpactAnalyzer


def _usage(
    *,
    symbol: str,
    fqn: str,
    kind: str,
    file_path: str = "src/app.py",
    line: int = 10,
    package: str = "pydantic",
) -> dict:
    return {
        "package_name": package,
        "symbol": symbol,
        "fully_qualified_name": fqn,
        "usage_kind": kind,
        "file_path": file_path,
        "line": line,
        "column": 0,
        "code_snippet": fqn,
        "enclosing_function": "handler",
        "enclosing_class": None,
    }


def test_version_crosses_major_threshold() -> None:
    assert version_crosses("1.10.0", "2.5.0", threshold="2.0.0") is True
    assert version_crosses("2.0.0", "2.5.0", threshold="2.0.0") is False
    assert version_crosses("1.10.0", "1.20.0", threshold="2.0.0") is False


def test_pydantic_upgrade_impact_matches_validator_usage() -> None:
    usages = [
        _usage(symbol="validator", fqn="pydantic.validator", kind="decorator", line=12),
        _usage(symbol="BaseModel", fqn="pydantic.BaseModel", kind="inheritance", line=8),
        _usage(symbol="dict", fqn="User.dict", kind="method_call", line=40),
    ]
    report = UpgradeImpactAnalyzer().analyze(
        package_name="pydantic",
        current_version="1.10.13",
        target_version="2.9.0",
        usages=usages,
    )
    assert report.analysis_source == "deterministic"
    assert report.catalog_rules_applied > 0
    assert report.breaking_findings
    apis = {f.affected_api for f in report.breaking_findings}
    assert "validator" in apis or ".dict" in apis or "dict" in {a.lstrip(".") for a in apis}
    # Evidence must include file/line
    assert any(f.evidence and f.evidence[0].file_path == "src/app.py" for f in report.findings)
    assert all(f.analysis_source == "deterministic" for f in report.findings)
    payload = report.to_simulation_payload()
    assert "breaking_apis" in payload
    assert payload["upgrade_impact"]["package_name"] == "pydantic"


def test_major_upgrade_without_usage_is_not_auto_breaking() -> None:
    report = UpgradeImpactAnalyzer().analyze(
        package_name="pydantic",
        current_version="1.10.0",
        target_version="2.0.0",
        usages=[],
    )
    assert report.breaking_findings == []
    assert "No AST usage" in report.summary


def test_fastapi_on_event_deprecated_when_used() -> None:
    usages = [
        _usage(
            package="fastapi",
            symbol="on_event",
            fqn="app.on_event",
            kind="method_call",
            file_path="src/main.py",
            line=22,
        ),
        _usage(
            package="fastapi",
            symbol="FastAPI",
            fqn="fastapi.FastAPI",
            kind="import",
            file_path="src/main.py",
            line=1,
        ),
    ]
    report = UpgradeImpactAnalyzer().analyze(
        package_name="fastapi",
        current_version="0.90.0",
        target_version="0.115.0",
        usages=usages,
    )
    assert report.catalog_rules_applied > 0
    deprecated = [f for f in report.findings if f.change_type == "deprecated"]
    assert deprecated
    assert deprecated[0].affected_api == "on_event"
    assert deprecated[0].evidence[0].line == 22
    assert "FastAPI" in report.unchanged_apis or any(
        f.affected_api == "FastAPI" for f in report.findings
    ) or "fastapi.FastAPI" not in report.unresolved_apis


def test_unknown_package_upgrade_marks_used_apis_unresolved() -> None:
    usages = [
        _usage(
            package="obscurelib",
            symbol="do_thing",
            fqn="obscurelib.do_thing",
            kind="function_call",
        )
    ]
    report = UpgradeImpactAnalyzer().analyze(
        package_name="obscurelib",
        current_version="1.0.0",
        target_version="2.0.0",
        usages=usages,
    )
    assert report.catalog_rules_applied == 0
    assert report.breaking_findings == []
    assert "obscurelib.do_thing" in report.unresolved_apis
    assert "unresolved" in report.summary.lower() or "No deterministic" in report.summary


def test_rules_for_upgrade_fastapi_threshold() -> None:
    rules = rules_for_upgrade("fastapi", "0.90.0", "0.115.0")
    assert any(r.symbol == "on_event" for r in rules)
    assert not rules_for_upgrade("fastapi", "0.95.0", "0.96.0")


def test_flask_before_first_request_removed() -> None:
    usages = [
        _usage(
            package="flask",
            symbol="before_first_request",
            fqn="app.before_first_request",
            kind="method_call",
            file_path="app.py",
            line=8,
        )
    ]
    report = UpgradeImpactAnalyzer().analyze(
        package_name="flask",
        current_version="2.2.0",
        target_version="3.0.0",
        usages=usages,
    )
    assert report.breaking_findings
    assert report.breaking_findings[0].affected_api == "before_first_request"
    assert report.breaking_findings[0].evidence[0].line == 8


def test_django_ugettext_removed() -> None:
    usages = [
        _usage(
            package="django",
            symbol="ugettext",
            fqn="django.utils.translation.ugettext",
            kind="import",
        )
    ]
    report = UpgradeImpactAnalyzer().analyze(
        package_name="django",
        current_version="3.2.0",
        target_version="4.2.0",
        usages=usages,
    )
    assert any(f.affected_api == "ugettext" for f in report.breaking_findings)
