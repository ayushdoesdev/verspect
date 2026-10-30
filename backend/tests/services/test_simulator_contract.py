"""Upgrade Simulator persistence contract — no-catalog AI merge vs legacy Unknown."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.migration_engine.models import MigrationFinding
from app.schemas.upgrade_simulation import enrich_simulation_response
from app.services.upgrade_helpers import findings_to_suggested_changes
from app.services.upgrade_intelligence.engine import DynamicUpgradeIntelligence
from app.services.upgrade_intelligence.evidence import EvidenceBundle
from app.services.upgrade_intelligence.simulator_contract import (
    INTELLIGENCE_SCHEMA_VERSION,
    apply_intelligence_to_simulator_findings,
    cached_simulation_is_current,
    is_legacy_catalog_unknown,
    simulator_confidence,
    simulator_summary,
)

LEGACY_PHRASE = "insufficient deterministic knowledge"
NO_CATALOG_PACKAGE = "@mui/x-data-grid"


class _SpyAI:
    available = True
    model = "spy"
    calls: list[tuple[str, str]]

    def __init__(
        self,
        payload=None,
        fail: bool = False,
        malformed: bool = False,
        timeout: bool = False,
    ) -> None:
        self.payload = payload
        self.fail = fail
        self.malformed = malformed
        self.timeout = timeout
        self.calls = []

    def _respond_json(self, system: str, user: str) -> dict:
        self.calls.append((system, user))
        if self.timeout:
            from app.ai.exceptions import AITimeoutError

            raise AITimeoutError("spy", "timed out")
        if self.fail:
            from app.ai.exceptions import AIProviderUnavailable

            raise AIProviderUnavailable("spy", "unreachable")
        if self.malformed:
            return {"nope": True}
        if self.payload is not None:
            return self.payload
        return {"categories": []}


def _usage(
    *,
    symbol: str,
    fqn: str,
    file_path: str = "src/app.py",
    line: int = 10,
    package: str = "demo",
    snippet: str | None = None,
) -> dict:
    return {
        "package_name": package,
        "symbol": symbol,
        "fully_qualified_name": fqn,
        "usage_kind": "call",
        "file_path": file_path,
        "line": line,
        "column": 0,
        "code_snippet": snippet or fqn,
        "module_path": package,
    }


def _bundle(package: str = "demo", ecosystem: str = "pypi") -> EvidenceBundle:
    return EvidenceBundle(
        package_name=package,
        ecosystem=ecosystem,
        from_version="1.0.0",
        to_version="2.0.0",
        extracted_changes=[],
        items=[],
        degradation=[],
        documentation_urls=[
            {"type": "changelog", "url": "https://example.test/changelog", "label": "Changelog"}
        ],
    )


def _catalog_unknown_findings() -> list[dict]:
    engine_findings = [
        MigrationFinding(
            status="unknown",
            file_path="src/Body.js",
            line=3,
            symbol=NO_CATALOG_PACKAGE,
            confidence=0.3,
            current_code="import { DataGrid } from '@mui/x-data-grid'",
            reason=(
                "Unknown — insufficient deterministic migration knowledge for this "
                "usage. Do not treat as a clean upgrade."
            ),
        ),
        MigrationFinding(
            status="unknown",
            file_path="(repository)",
            symbol=NO_CATALOG_PACKAGE,
            confidence=0.3,
            reason=(
                "Unknown — no structured migration rules are available for this "
                "library/version range. Insufficient deterministic knowledge."
            ),
        ),
    ]
    return findings_to_suggested_changes(engine_findings)


def _ai_payload() -> dict:
    return {
        "categories": [
            {
                "category": "breaking_changes",
                "answer": "Column API typing tightened; review DataGrid props used in the repo.",
                "status": "likely",
                "findings": [
                    {
                        "category": "breaking_changes",
                        "finding": "DataGrid",
                        "explanation": "Documented typing and slot changes in this range.",
                        "affected_files": [
                            {
                                "file": "src/Body.js",
                                "line": 3,
                                "api": "DataGrid",
                                "reason": "imported in repository",
                            }
                        ],
                        "required_change": "Review DataGrid props at src/Body.js:3 against the target types.",
                        "confidence": 0.68,
                        "evidence": ["changelog: DataGrid slots/types"],
                        "status": "likely",
                    }
                ],
            },
            {
                "category": "migration_rules",
                "answer": "No structured catalog rules; follow official Grid upgrade notes.",
                "status": "possible",
                "findings": [
                    {
                        "category": "migration_rules",
                        "finding": "Follow official Data Grid upgrade notes for this range.",
                        "explanation": "Catalog has no structured rules; AI filled this category from docs.",
                        "confidence": 0.6,
                        "evidence": ["docs: upgrade guide"],
                        "status": "possible",
                    }
                ],
            },
        ]
    }


def _analyze(*, allow_ai: bool, ai, usages, evidence: EvidenceBundle | None = None):
    return DynamicUpgradeIntelligence().analyze(
        package_name=NO_CATALOG_PACKAGE,
        current_version="6.0.0",
        target_version="7.0.0",
        usages=usages,
        ecosystem="npm",
        allow_ai=allow_ai,
        ai=ai,
        evidence=evidence or _bundle(NO_CATALOG_PACKAGE, "npm"),
        skip_network=True,
    )


def _usages():
    return [
        _usage(
            symbol="DataGrid",
            fqn="@mui/x-data-grid.DataGrid",
            file_path="src/Body.js",
            line=3,
            package=NO_CATALOG_PACKAGE,
            snippet="import { DataGrid } from '@mui/x-data-grid'",
        )
    ]


def _legacy_blob(rows: list[dict]) -> str:
    return " ".join(
        f"{r.get('status_title') or ''} {r.get('status_detail') or ''} {r.get('explanation') or ''}"
        for r in rows
    ).lower()


def test_engine_unknown_rows_are_legacy_catalog_unknown() -> None:
    rows = _catalog_unknown_findings()
    assert rows
    assert all(is_legacy_catalog_unknown(r) for r in rows)
    assert LEGACY_PHRASE in _legacy_blob(rows)


def test_no_catalog_ai_entitled_merged_findings_are_not_legacy_unknown() -> None:
    """The original Upgrade Simulator bug: missing catalog + AI entitled + valid AI.

    Intelligence required_changes can be empty (import-only). The simulator
    contract must still replace catalog-Unknown cards with merged findings.
    """
    spy = _SpyAI(payload=_ai_payload())
    suggested = _catalog_unknown_findings()
    report = _analyze(allow_ai=True, ai=spy, usages=_usages())
    assert spy.calls, "AI must be invoked when the catalog is empty and the plan allows AI"
    assert report.ai_invoked is True

    merged = apply_intelligence_to_simulator_findings(
        suggested, report, package_name=NO_CATALOG_PACKAGE
    )
    assert merged
    assert not any(is_legacy_catalog_unknown(r) for r in merged)
    assert LEGACY_PHRASE not in _legacy_blob(merged)
    assert "no structured migration rules" not in _legacy_blob(merged)
    assert any(r.get("analysis_source") for r in merged)
    assert any(r.get("file_path") == "src/Body.js" for r in merged)
    assert all((r.get("status_title") or "") != "Unknown" for r in merged)


def test_no_catalog_ai_merge_survives_api_enrichment() -> None:
    spy = _SpyAI(payload=_ai_payload())
    report = _analyze(allow_ai=True, ai=spy, usages=_usages())
    merged = apply_intelligence_to_simulator_findings(
        _catalog_unknown_findings(), report, package_name=NO_CATALOG_PACKAGE
    )
    now = datetime.now(timezone.utc)
    sim = SimpleNamespace(
        id=uuid4(),
        created_at=now,
        updated_at=now,
        dependency_id=uuid4(),
        repository_id=uuid4(),
        triggered_by_user_id=None,
        package_name=NO_CATALOG_PACKAGE,
        from_version="6.0.0",
        to_version="7.0.0",
        status="completed",
        progress_percent=100,
        current_stage="completed",
        celery_task_id=None,
        summary=simulator_summary(report, engine_summary="Unknown — no structured migration rules."),
        safe_to_upgrade=False,
        confidence=simulator_confidence(report, engine_confidence=0.3, catalog_matched=False),
        readiness_score=55.0,
        risk_score=45.0,
        migration_time_hours=2.0,
        migration_time_label="~2 hours",
        breaking_apis=[],
        deprecated_apis=[],
        affected_files=[],
        affected_symbols=[],
        affected_functions=[],
        affected_classes=[],
        security_improvements=[],
        performance_improvements=[],
        manual_work_required=[],
        automatic_fixes_possible=[],
        migration_plan=[],
        suggested_changes=merged,
        readiness_factors={},
        migration_rules=[],
        official_references=[],
        engine_report_id=None,
        collected_sources={
            "dynamic_intelligence": report.model_dump(),
            "breaking_classification": report.breaking_classification,
            "analysis_method": report.analysis_method,
            "ai_invoked": report.ai_invoked,
            "ai_skipped_reason": report.ai_skipped_reason,
            "intelligence_schema_version": INTELLIGENCE_SCHEMA_VERSION,
        },
        dynamic_intelligence=None,
        breaking_classification=None,
        analysis_method=None,
        ai_invoked=None,
        ai_skipped_reason=None,
        model_used=None,
        error_message=None,
        queued_at=now,
        started_at=now,
        completed_at=now,
        duration_seconds=1.0,
        last_heartbeat_at=None,
        worker_name=None,
        retry_count=0,
        cancel_requested=False,
        stage_timings=[],
        raw_ai_response={},
    )
    response = enrich_simulation_response(sim)
    assert response.dynamic_intelligence
    assert response.dynamic_intelligence.get("categories")
    assert response.ai_invoked is True
    assert response.analysis_method in {"ai", "deterministic+ai"}
    blob = str(response.suggested_changes).lower() + " " + (response.summary or "").lower()
    assert LEGACY_PHRASE not in blob
    assert "no structured migration rules" not in blob
    assert cached_simulation_is_current(sim) is True


def test_complete_deterministic_catalog_findings_are_kept() -> None:
    spy = _SpyAI()
    usages = [
        _usage(symbol="validator", fqn="pydantic.validator", package="pydantic", line=12),
        _usage(symbol="BaseModel", fqn="pydantic.BaseModel", package="pydantic", line=8),
    ]
    usages[0]["usage_kind"] = "decorator"
    usages[1]["usage_kind"] = "inheritance"
    report = DynamicUpgradeIntelligence().analyze(
        package_name="pydantic",
        current_version="1.10.13",
        target_version="2.9.0",
        usages=usages,
        ecosystem="pypi",
        allow_ai=True,
        ai=spy,
        evidence=_bundle("pydantic", "pypi"),
        skip_network=True,
    )
    assert spy.calls == []
    catalog_row = {
        "file_path": "src/app.py",
        "line": 12,
        "symbol": "validator",
        "explanation": "Replace @validator with @field_validator.",
        "migration_status": "manual_review_required",
        "status_title": "Manual review required",
        "confidence": 0.9,
        "unknown": False,
        "automatic": False,
        "current_code": "@validator",
        "suggested_code": None,
    }
    merged = apply_intelligence_to_simulator_findings(
        [catalog_row], report, package_name="pydantic"
    )
    assert any(r.get("symbol") == "validator" for r in merged)
    assert not any(is_legacy_catalog_unknown(r) for r in merged)
    compatible = {
        "file_path": "src/app.py",
        "line": 8,
        "symbol": "BaseModel",
        "explanation": "No changes required — API remains compatible.",
        "status_detail": "No changes required — API remains compatible.",
        "migration_status": "no_migration_required",
        "status_title": "No changes required",
        "confidence": 0.95,
        "unknown": False,
        "automatic": False,
        "current_code": "class M(BaseModel):",
        "suggested_code": None,
    }
    merged_ok = apply_intelligence_to_simulator_findings(
        [catalog_row, compatible], report, package_name="pydantic"
    )
    assert any(
        r.get("symbol") == "BaseModel" and r.get("migration_status") == "no_migration_required"
        for r in merged_ok
    )


def test_plan_without_ai_does_not_claim_catalog_unknown() -> None:
    spy = _SpyAI(payload=_ai_payload())
    report = _analyze(allow_ai=False, ai=spy, usages=_usages())
    assert spy.calls == []
    merged = apply_intelligence_to_simulator_findings(
        _catalog_unknown_findings(), report, package_name=NO_CATALOG_PACKAGE
    )
    blob = _legacy_blob(merged)
    assert LEGACY_PHRASE not in blob
    assert "plan" in blob or "pro" in blob or "deterministic analysis" in blob


def test_ai_unavailable_preserves_usage_and_does_not_use_catalog_unknown() -> None:
    spy = _SpyAI(fail=True)
    report = _analyze(allow_ai=True, ai=spy, usages=_usages())
    merged = apply_intelligence_to_simulator_findings(
        _catalog_unknown_findings(), report, package_name=NO_CATALOG_PACKAGE
    )
    blob = _legacy_blob(merged)
    assert LEGACY_PHRASE not in blob
    assert "unavailable" in blob
    assert any(r.get("file_path") == "src/Body.js" for r in merged)
    assert any(r.get("migration_status") == "unresolved" for r in merged)


def test_ai_timeout_is_not_malformed_or_unavailable() -> None:
    spy = _SpyAI(timeout=True)
    report = _analyze(allow_ai=True, ai=spy, usages=_usages())
    assert "ai_timeout" in report.degradation
    assert "malformed_ai_response" not in report.degradation
    merged = apply_intelligence_to_simulator_findings(
        _catalog_unknown_findings(), report, package_name=NO_CATALOG_PACKAGE
    )
    blob = _legacy_blob(merged)
    assert LEGACY_PHRASE not in blob
    assert "timed out" in blob
    assert "unavailable" not in blob
    assert any(r.get("file_path") == "src/Body.js" for r in merged)
    assert any((r.get("status_title") or "") == "AI-assisted analysis timed out" for r in merged)


def test_malformed_ai_does_not_leave_catalog_unknown() -> None:
    spy = _SpyAI(malformed=True)
    report = _analyze(allow_ai=True, ai=spy, usages=_usages())
    merged = apply_intelligence_to_simulator_findings(
        _catalog_unknown_findings(), report, package_name=NO_CATALOG_PACKAGE
    )
    blob = _legacy_blob(merged)
    assert LEGACY_PHRASE not in blob
    assert "malformed" in blob
    assert "unavailable" not in blob


def test_engine_unmatched_no_change_is_not_a_clean_upgrade() -> None:
    spy = _SpyAI(timeout=True)
    report = _analyze(allow_ai=True, ai=spy, usages=_usages())
    engine_row = {
        "file_path": "src/Body.js",
        "line": 3,
        "symbol": NO_CATALOG_PACKAGE,
        "explanation": (
            "No changes required — deterministic migration rules exist for this "
            "range and none match this usage."
        ),
        "status_detail": (
            "No changes required — deterministic migration rules exist for this "
            "range and none match this usage."
        ),
        "migration_status": "no_migration_required",
        "status_title": "No changes required",
        "confidence": 1.0,
        "unknown": False,
        "automatic": False,
        "current_code": "import { DataGrid } from '@mui/x-data-grid'",
        "suggested_code": None,
    }
    merged = apply_intelligence_to_simulator_findings(
        [engine_row], report, package_name=NO_CATALOG_PACKAGE
    )
    assert any(r.get("migration_status") == "unresolved" for r in merged)
    assert not any(r.get("migration_status") == "no_migration_required" for r in merged)
    assert "not a verified clean upgrade" in _legacy_blob(merged)


def test_stale_completed_simulation_is_not_current() -> None:
    stale = SimpleNamespace(
        collected_sources={
            "dynamic_intelligence": None,
        }
    )
    assert cached_simulation_is_current(stale) is False
    pre_intel = SimpleNamespace(
        collected_sources={
            "intelligence_schema_version": 1,
            "dynamic_intelligence": {"categories": {"breaking_changes": {}}},
        }
    )
    assert cached_simulation_is_current(pre_intel) is False
    current = SimpleNamespace(
        collected_sources={
            "intelligence_schema_version": INTELLIGENCE_SCHEMA_VERSION,
            "dynamic_intelligence": {"categories": {"breaking_changes": {}}},
        }
    )
    assert cached_simulation_is_current(current) is True
    timed_out = SimpleNamespace(
        collected_sources={
            "intelligence_schema_version": INTELLIGENCE_SCHEMA_VERSION,
            "ai_skipped_reason": "ai_timeout",
            "dynamic_intelligence": {
                "categories": {"breaking_changes": {}},
                "degradation": ["ai_timeout"],
                "ai_skipped_reason": "ai_timeout",
            },
        }
    )
    assert cached_simulation_is_current(timed_out) is False
    unavailable = SimpleNamespace(
        collected_sources={
            "intelligence_schema_version": INTELLIGENCE_SCHEMA_VERSION,
            "dynamic_intelligence": {
                "categories": {"breaking_changes": {}},
                "degradation": ["ai_unavailable"],
            },
        }
    )
    assert cached_simulation_is_current(unavailable) is False
    refreshed = SimpleNamespace(
        collected_sources={
            "intelligence_schema_version": INTELLIGENCE_SCHEMA_VERSION,
            "dynamic_intelligence": {
                "categories": {"breaking_changes": {"completeness": "partial"}},
                "degradation": [],
                "ai_invoked": True,
            },
        }
    )
    assert cached_simulation_is_current(refreshed) is True


def test_simulator_summary_rejects_engine_catalog_unknown() -> None:
    spy = _SpyAI(payload=_ai_payload())
    report = _analyze(allow_ai=True, ai=spy, usages=_usages())
    summary = simulator_summary(
        report,
        engine_summary="Unknown — no structured migration rules are available.",
        catalog_matched=False,
    )
    assert "no structured migration rules" not in summary.lower()
    assert report.summary
    assert summary == report.summary
