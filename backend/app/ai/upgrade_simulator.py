"""AI engine for Upgrade Impact Simulator — structured, validated JSON only."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from pydantic import ValidationError

from app.ai.analyzer import AIAnalyzer
from app.ai.prompts import PromptTemplates
from app.core.logging import get_logger
from app.schemas.upgrade_simulation import (
    BreakingAPIItem,
    DeprecatedAPIItem,
    FileImpactItem,
    MigrationPhaseItem,
    ReadinessFactors,
    SuggestedChangeItem,
    UpgradeImpactAIResult,
)

logger = get_logger(__name__)


def build_cache_key(
    dependency_id: str,
    from_version: str,
    to_version: str,
    usage_fingerprint: str,
) -> str:
    raw = f"{dependency_id}|{from_version}|{to_version}|{usage_fingerprint}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


def usage_fingerprint(usages: list[dict[str, Any]]) -> str:
    keys = sorted(
        {
            f"{u.get('fully_qualified_name')}|{u.get('file_path')}|{u.get('line')}"
            for u in usages
        }
    )
    return hashlib.sha256("|".join(keys).encode()).hexdigest()[:32]


class UpgradeImpactAnalyzer:
    """Compare AST usage against upgrade sources and produce a validated report."""

    def __init__(
        self,
        ai: Optional[AIAnalyzer] = None,
        *,
        allow_ai: bool = True,
    ) -> None:
        """When ``allow_ai`` is False (Evaluation/Starter), use deterministic fallback only."""
        from app.ai.analyzer import DisabledAIAnalyzer

        self.allow_ai = allow_ai
        if allow_ai:
            self.ai = ai if ai is not None else AIAnalyzer()
        else:
            self.ai = ai if ai is not None else DisabledAIAnalyzer()

    def analyze(
        self,
        *,
        package_name: str,
        from_version: str,
        to_version: str,
        usages: list[dict[str, Any]],
        sources: dict[str, Any],
        cve_fixed_hints: Optional[list[str]] = None,
    ) -> UpgradeImpactAIResult:
        if not self.allow_ai or not self.ai.available:
            return self._fallback(package_name, from_version, to_version, usages, sources)

        payload = {
            "package_name": package_name,
            "from_version": from_version,
            "to_version": to_version,
            "api_usages": usages[:400],
            "collected_sources": {
                "release_notes": (sources.get("release_notes") or [])[:15],
                "breaking_change_hints": (sources.get("breaking_change_hints") or [])[:50],
                "deprecated_hints": (sources.get("deprecated_hints") or [])[:50],
                "security_fixes": (sources.get("security_fixes") or [])[:30],
                "github_releases": [
                    {
                        "tag": g.get("tag"),
                        "name": g.get("name"),
                        "body": (g.get("body") or "")[:4000],
                    }
                    for g in (sources.get("github_releases") or [])[:10]
                ],
                "documentation_urls": sources.get("documentation_urls") or [],
                "pypi_summary": (sources.get("pypi") or {}).get("summary"),
            },
            "cve_fixed_hints": cve_fixed_hints or [],
            "output_schema": {
                "summary": "string",
                "safe_to_upgrade": "boolean",
                "confidence": "0-1 float",
                "readiness_score": "0-100 float",
                "risk_score": "0-100 float",
                "migration_time_hours": "float",
                "migration_time_label": "string",
                "breaking_apis": [
                    {
                        "symbol": "str",
                        "fully_qualified_name": "str",
                        "severity": "critical|high|medium|low|info",
                        "reason": "str",
                        "replacement": "str|null",
                        "confidence": "0-1",
                    }
                ],
                "deprecated_apis": [
                    {
                        "symbol": "str",
                        "fully_qualified_name": "str",
                        "reason": "str",
                        "replacement": "str|null",
                        "removal_version": "str|null",
                        "confidence": "0-1",
                    }
                ],
                "affected_files": [
                    {
                        "file_path": "str",
                        "affected_apis": ["str"],
                        "reason": "str",
                        "confidence": "0-1",
                        "suggested_changes": ["str"],
                        "enclosing_functions": ["str"],
                        "enclosing_classes": ["str"],
                    }
                ],
                "affected_symbols": ["str"],
                "affected_functions": ["str"],
                "affected_classes": ["str"],
                "security_improvements": ["str"],
                "performance_improvements": ["str"],
                "manual_work_required": ["str"],
                "automatic_fixes_possible": ["str"],
                "migration_plan": [
                    {
                        "phase": 1,
                        "title": "str",
                        "description": "str",
                        "reasoning": "str",
                        "difficulty": "trivial|low|medium|high|very_high",
                        "estimated_duration_hours": 1.0,
                        "tasks": ["str"],
                    }
                ],
                "suggested_changes": [
                    {
                        "file_path": "str",
                        "line": 1,
                        "symbol": "str",
                        "current_code": "str",
                        "suggested_code": "str",
                        "explanation": "str",
                        "confidence": "0-1",
                        "automatic": False,
                    }
                ],
                "readiness_factors": {
                    "breaking_apis": "0-100",
                    "plugin_compatibility": "0-100",
                    "deprecated_calls": "0-100",
                    "security": "0-100",
                    "tests": "0-100",
                },
            },
        }

        user = PromptTemplates.upgrade_impact_user(payload)
        raw = self.ai._respond_json(PromptTemplates.upgrade_impact_system(), user)
        return self._validate(raw, package_name, from_version, to_version, usages, sources)

    def _validate(
        self,
        raw: dict[str, Any],
        package_name: str,
        from_version: str,
        to_version: str,
        usages: list[dict[str, Any]],
        sources: dict[str, Any],
    ) -> UpgradeImpactAIResult:
        try:
            return UpgradeImpactAIResult.model_validate(raw)
        except ValidationError as exc:
            logger.warning("upgrade_ai_validation_failed", error=str(exc))
            # Attempt partial repair
            repaired = self._repair(raw, usages)
            try:
                return UpgradeImpactAIResult.model_validate(repaired)
            except ValidationError:
                return self._fallback(package_name, from_version, to_version, usages, sources)

    def _repair(self, raw: dict[str, Any], usages: list[dict[str, Any]]) -> dict[str, Any]:
        data = dict(raw) if isinstance(raw, dict) else {}
        data.setdefault("summary", "Upgrade impact analysis completed with partial AI output.")
        data.setdefault("safe_to_upgrade", False)
        data.setdefault("confidence", 0.4)
        data.setdefault("readiness_score", 45.0)
        data.setdefault("risk_score", 55.0)
        data.setdefault("migration_time_hours", 4.0)
        data.setdefault("migration_time_label", "~4 hours")
        data.setdefault("breaking_apis", [])
        data.setdefault("deprecated_apis", [])
        data.setdefault("affected_files", [])
        data.setdefault("affected_symbols", [])
        data.setdefault("affected_functions", [])
        data.setdefault("affected_classes", [])
        data.setdefault("security_improvements", [])
        data.setdefault("performance_improvements", [])
        data.setdefault("manual_work_required", ["Review AI output manually — validation repaired fields."])
        data.setdefault("automatic_fixes_possible", [])
        data.setdefault(
            "migration_plan",
            [
                {
                    "phase": 1,
                    "title": "Review and pin target version",
                    "description": "Confirm target version and run test suite.",
                    "reasoning": "Baseline safety before code changes.",
                    "difficulty": "low",
                    "estimated_duration_hours": 1.0,
                    "tasks": ["Update pin", "Install", "Run tests"],
                }
            ],
        )
        data.setdefault("suggested_changes", [])
        data.setdefault("readiness_factors", ReadinessFactors().model_dump())

        # Ensure list items are dict-shaped when possible
        if not data.get("affected_symbols"):
            data["affected_symbols"] = sorted(
                {u.get("fully_qualified_name") for u in usages if u.get("fully_qualified_name")}
            )[:100]
        # Never leave affected_files empty when AST usages exist
        if not data.get("affected_files") and usages:
            from app.services.upgrade_helpers import build_ast_affected_files

            data["affected_files"] = build_ast_affected_files(usages)
        return data

    def _fallback(
        self,
        package_name: str,
        from_version: str,
        to_version: str,
        usages: list[dict[str, Any]],
        sources: dict[str, Any],
    ) -> UpgradeImpactAIResult:
        symbols = sorted(
            {u.get("fully_qualified_name") for u in usages if u.get("fully_qualified_name")}
        )
        functions = sorted(
            {u.get("enclosing_function") for u in usages if u.get("enclosing_function")}
        )
        classes = sorted(
            {u.get("enclosing_class") for u in usages if u.get("enclosing_class")}
        )

        # Heuristic: match usage symbols against breaking/deprecated hints text
        hints = " ".join(
            str(x).lower()
            for x in (sources.get("breaking_change_hints") or [])
            + (sources.get("deprecated_hints") or [])
            + [n.get("text", "")[:2000] for n in (sources.get("release_notes") or [])[:5]]
        )

        breaking: list[BreakingAPIItem] = []
        deprecated: list[DeprecatedAPIItem] = []
        for sym in symbols:
            leaf = (sym or "").split(".")[-1].lower()
            if leaf and leaf in hints and any(
                k in hints for k in ("breaking", "removed", "incompatible")
            ):
                breaking.append(
                    BreakingAPIItem(
                        symbol=leaf,
                        fully_qualified_name=sym,
                        severity="high",
                        reason="Mentioned near breaking-change language in collected sources.",
                        confidence=0.45,
                    )
                )
            elif leaf and "deprecat" in hints and leaf in hints:
                deprecated.append(
                    DeprecatedAPIItem(
                        symbol=leaf,
                        fully_qualified_name=sym,
                        reason="Mentioned near deprecation language in collected sources.",
                        confidence=0.4,
                    )
                )

        # File impacts — AST is source of truth: every usage file, always
        from app.services.upgrade_helpers import build_ast_affected_files, rule_annotations_by_file

        matched_for_ann = [
            {
                "file_path": u.get("file_path"),
                "symbol": b.fully_qualified_name,
                "kind": "breaking",
                "severity": b.severity,
                "description": b.reason,
                "confidence": b.confidence,
            }
            for b in breaking
            for u in usages
            if u.get("fully_qualified_name") == b.fully_qualified_name
        ] + [
            {
                "file_path": u.get("file_path"),
                "symbol": d.fully_qualified_name,
                "kind": "deprecated",
                "severity": "medium",
                "description": d.reason,
                "confidence": d.confidence,
            }
            for d in deprecated
            for u in usages
            if u.get("fully_qualified_name") == d.fully_qualified_name
        ]
        files_list = build_ast_affected_files(
            usages,
            rule_annotations=rule_annotations_by_file(matched_for_ann),
        )
        files_map_items = [
            FileImpactItem(
                file_path=f["file_path"],
                affected_apis=f.get("affected_apis") or [],
                reason=f.get("reason") or "AST usage",
                confidence=float(f.get("confidence") or 0.9),
                enclosing_functions=f.get("enclosing_functions") or [],
                enclosing_classes=f.get("enclosing_classes") or [],
                suggested_changes=[],
            )
            for f in files_list
        ]

        # Manual-review suggestions for risk-flagged usages only (never fabricate replacements)
        suggestions: list[SuggestedChangeItem] = []
        affected_fqns = {b.fully_qualified_name for b in breaking} | {
            d.fully_qualified_name for d in deprecated
        }
        for u in usages:
            fqn = u.get("fully_qualified_name")
            if fqn not in affected_fqns:
                continue
            path = u.get("file_path") or "unknown"
            snippet = u.get("code_snippet") or fqn
            suggestions.append(
                SuggestedChangeItem(
                    file_path=path,
                    line=u.get("line"),
                    symbol=fqn,
                    current_code=snippet,
                    suggested_code=snippet,  # identical — UI/backend classify as manual, no fake diff
                    explanation=(
                        f"Usage of {fqn} may be affected. Manual review required — "
                        f"no high-confidence automatic patch."
                    ),
                    confidence=0.4,
                    automatic=False,
                )
            )

        major_jump = False
        try:
            from packaging.version import Version

            major_jump = Version(to_version).major > Version(from_version).major
        except Exception:
            major_jump = True

        breaking_count = len(breaking)
        readiness = 80.0
        readiness -= min(50.0, breaking_count * 12)
        if major_jump:
            readiness -= 15
        readiness = max(5.0, min(100.0, readiness))
        risk = max(5.0, min(100.0, 100.0 - readiness + breaking_count * 5))

        hours = 1.0 + breaking_count * 1.5 + (4.0 if major_jump else 0.5) + len(files_map_items) * 0.25
        security = list(sources.get("security_fixes") or [])[:10]
        if not security:
            security = ["No explicit security fix notes collected for this range."]

        plan = [
            MigrationPhaseItem(
                phase=1,
                title=f"Upgrade {package_name} to a safe intermediate/patch if available",
                description=f"Move carefully from {from_version} toward {to_version}.",
                reasoning="Incremental upgrades reduce blast radius.",
                difficulty="low" if not major_jump else "medium",
                estimated_duration_hours=round(hours * 0.25, 1),
                tasks=["Update version pin", "Install in a branch", "Run unit tests"],
            ),
            MigrationPhaseItem(
                phase=2,
                title="Address deprecated and breaking API usages",
                description="Fix call sites identified in the usage index.",
                reasoning="Code-aware changes unblock the major jump.",
                difficulty="medium" if breaking_count else "low",
                estimated_duration_hours=round(hours * 0.5, 1),
                tasks=[
                    "Update imports/calls for affected symbols",
                    "Replace deprecated APIs",
                    "Re-run targeted tests",
                ],
            ),
            MigrationPhaseItem(
                phase=3,
                title=f"Complete upgrade to {to_version} and verify",
                description="Land on the target version and validate.",
                reasoning="Final confirmation of readiness.",
                difficulty="high" if major_jump and breaking_count else "medium",
                estimated_duration_hours=round(hours * 0.25, 1),
                tasks=["Pin exact target", "Full regression", "Deploy to staging"],
            ),
        ]

        return UpgradeImpactAIResult(
            summary=(
                f"Simulated upgrade of {package_name} from {from_version} to {to_version}. "
                f"Found {len(usages)} usage sites across {len(files_map_items)} files. "
                f"{breaking_count} potential breaking API signals and {len(deprecated)} deprecation signals detected "
                f"via heuristic analysis"
                + (
                    " (AI provider unavailable — using deterministic fallback)."
                    if not self.ai.available
                    else "."
                )
            ),
            safe_to_upgrade=breaking_count == 0 and not major_jump,
            confidence=0.55 if self.ai.available else 0.4,
            readiness_score=round(readiness, 1),
            risk_score=round(risk, 1),
            migration_time_hours=round(hours, 1),
            migration_time_label=f"~{round(hours, 1)} hours",
            breaking_apis=breaking,
            deprecated_apis=deprecated,
            affected_files=files_map_items,
            affected_symbols=list(affected_fqns) or symbols[:50],
            affected_functions=functions[:50],
            affected_classes=classes[:50],
            security_improvements=security,
            performance_improvements=[],
            manual_work_required=[
                "Review each suggested change in context",
                "Run the full test suite after upgrading",
            ]
            + ([f"Resolve {breaking_count} breaking API usages"] if breaking_count else []),
            automatic_fixes_possible=[
                s.symbol for s in suggestions if s.automatic and s.symbol
            ],
            migration_plan=plan,
            suggested_changes=suggestions[:40],
            readiness_factors=ReadinessFactors(
                breaking_apis=max(0.0, 100.0 - breaking_count * 20),
                plugin_compatibility=60.0 if major_jump else 80.0,
                deprecated_calls=max(0.0, 100.0 - len(deprecated) * 15),
                security=75.0 if security else 50.0,
                tests=50.0,
            ),
        )
