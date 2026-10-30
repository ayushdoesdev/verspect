"""Deterministic Python Upgrade Impact Analysis.

Compares catalog/KB migration rules against real repository AST usage.
Does NOT classify every major upgrade as breaking.
Does NOT invent API changes — only structured rules with evidence.

Unresolved used APIs (no matching rule) are reported as `unresolved` for
optional later AI reasoning — never as verified breaking changes.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.migration_engine.models import MatchedUsage, MigrationRuleDTO
from app.migration_engine.rule_catalog import official_references_for, rules_for_upgrade
from app.migration_engine.rule_matcher import RuleMatcher
from app.migration_engine.semantic_index import SemanticASTIndex
from app.scanners.normalize import normalize_package_name
from app.services.upgrade_helpers import build_ast_affected_files, rule_annotations_by_file

AnalysisSource = Literal["deterministic", "hybrid", "ai"]
ChangeType = Literal[
    "removed",
    "renamed",
    "signature_change",
    "behavior_change",
    "deprecated",
    "import_path_change",
    "added",
    "unresolved",
    "unchanged",
]


class ImpactEvidence(BaseModel):
    file_path: str
    line: Optional[int] = None
    column: Optional[int] = None
    symbol: Optional[str] = None
    fully_qualified_name: Optional[str] = None
    usage_kind: Optional[str] = None
    code_snippet: Optional[str] = None
    enclosing_function: Optional[str] = None
    enclosing_class: Optional[str] = None


class UpgradeImpactFinding(BaseModel):
    dependency: str
    current_version: str
    target_version: str
    change_type: str
    affected_api: str
    description: str
    affected_files: list[str] = Field(default_factory=list)
    evidence: list[ImpactEvidence] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    analysis_source: AnalysisSource = "deterministic"
    official_reference: Optional[str] = None
    before: Optional[str] = None
    after: Optional[str] = None
    severity: Optional[str] = None
    is_breaking: bool = False
    auto_fixable: bool = False


class UpgradeImpactReport(BaseModel):
    package_name: str
    normalized_name: str
    current_version: str
    target_version: str
    analysis_source: AnalysisSource = "deterministic"
    catalog_rules_applied: int = 0
    usage_sites: int = 0
    used_apis: list[str] = Field(default_factory=list)
    findings: list[UpgradeImpactFinding] = Field(default_factory=list)
    breaking_findings: list[UpgradeImpactFinding] = Field(default_factory=list)
    unresolved_apis: list[str] = Field(default_factory=list)
    unchanged_apis: list[str] = Field(default_factory=list)
    affected_files: list[dict[str, Any]] = Field(default_factory=list)
    official_references: list[dict[str, str]] = Field(default_factory=list)
    analysis_limitations: list[str] = Field(default_factory=list)
    summary: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    def to_simulation_payload(self) -> dict[str, Any]:
        """Shape compatible with UpgradeSimulation JSONB fields."""
        breaking = []
        deprecated = []
        for f in self.findings:
            row = {
                "api": f.affected_api,
                "symbol": f.affected_api,
                "change_type": f.change_type,
                "kind": f.change_type,
                "description": f.description,
                "severity": f.severity,
                "confidence": f.confidence,
                "analysis_source": f.analysis_source,
                "official_reference": f.official_reference,
                "before": f.before,
                "after": f.after,
                "is_breaking": f.is_breaking,
                "affected_files": f.affected_files,
                "evidence": [e.model_dump() for e in f.evidence],
            }
            if f.change_type == "deprecated":
                deprecated.append(row)
            elif f.is_breaking:
                breaking.append(row)
        return {
            "breaking_apis": breaking,
            "deprecated_apis": deprecated,
            "affected_files": self.affected_files,
            "used_apis": self.used_apis,
            "unresolved_apis": self.unresolved_apis,
            "unchanged_apis": self.unchanged_apis,
            "upgrade_impact": self.model_dump(),
            "summary": self.summary,
            "confidence": self.confidence,
            "analysis_source": self.analysis_source,
            "official_references": self.official_references,
        }


_BREAKING_KINDS = {
    "removed",
    "renamed",
    "signature_change",
    "behavior_change",
    "import_path_change",
}


class UpgradeImpactAnalyzer:
    """Deterministic upgrade impact — rules × repository usage evidence."""

    def __init__(self, matcher: Optional[RuleMatcher] = None) -> None:
        self.matcher = matcher or RuleMatcher()

    def analyze(
        self,
        *,
        package_name: str,
        current_version: str,
        target_version: str,
        usages: list[dict[str, Any]],
        extra_rules: Optional[list[MigrationRuleDTO]] = None,
    ) -> UpgradeImpactReport:
        norm = normalize_package_name(package_name)
        catalog = rules_for_upgrade(package_name, current_version, target_version)
        rules = list(catalog)
        if extra_rules:
            rules.extend(extra_rules)

        index = SemanticASTIndex.from_usage_dicts(usages).filter_package(package_name)
        used_apis = sorted(
            {
                (n.fully_qualified_name or n.symbol or "").strip()
                for n in index.nodes
                if (n.fully_qualified_name or n.symbol)
            }
        )
        matches = self.matcher.match_index(index, rules) if rules else []

        findings = self._findings_from_matches(
            package_name=package_name,
            current_version=current_version,
            target_version=target_version,
            matches=matches,
        )

        matched_symbols = {
            (m.rule.symbol or "").lower().lstrip(".")
            for m in matches
        } | {
            (m.fully_qualified_name or "").split(".")[-1].lower()
            for m in matches
        }

        unchanged: list[str] = []
        for rule in rules:
            if not rule.unchanged:
                continue
            sym = (rule.symbol or "").lower()
            if any(sym in (a or "").lower() or (a.split(".")[-1] or "").lower() == sym for a in used_apis):
                unchanged.append(rule.symbol)
                matched_symbols.add(sym)

        unresolved: list[str] = []
        for api in used_apis:
            leaf = (api.split(".")[-1] or "").lower()
            if leaf in matched_symbols:
                continue
            if any(
                (r.symbol or "").lower().lstrip(".") == leaf
                or leaf in (r.symbol or "").lower()
                for r in rules
            ):
                continue
            unresolved.append(api)

        annotations = rule_annotations_by_file(matches)
        affected_files = build_ast_affected_files(usages, rule_annotations=annotations)

        breaking = [f for f in findings if f.is_breaking]
        refs = official_references_for(package_name)

        if not usages:
            summary = (
                f"No AST usage of {package_name} was found in the repository. "
                "Cannot confirm upgrade impact from repository evidence."
            )
            confidence = 0.4
        elif not rules:
            summary = (
                f"No deterministic migration rules are registered for "
                f"{package_name} {current_version} → {target_version}. "
                f"{len(used_apis)} used API(s) remain unresolved pending documentation "
                "or AI reasoning."
            )
            confidence = 0.35
        elif breaking:
            summary = (
                f"Found {len(breaking)} potential breaking change(s) with repository "
                f"evidence across {len(affected_files)} file(s)."
            )
            confidence = min(
                0.99,
                max(f.confidence for f in breaking),
            )
        else:
            summary = (
                f"No breaking API matches for used symbols under deterministic rules "
                f"for {package_name} {current_version} → {target_version}."
            )
            confidence = 0.85 if catalog else 0.5

        # Deduplicate unresolved preserving order
        seen_u: set[str] = set()
        unresolved_unique: list[str] = []
        for a in unresolved:
            if a not in seen_u:
                seen_u.add(a)
                unresolved_unique.append(a)

        limitations: list[str] = []
        if not catalog:
            limitations.append(
                "No deterministic migration catalog rules are registered for this package "
                "and version range. Used APIs without matching rules are unresolved, not breaking."
            )
        if unresolved_unique:
            limitations.append(
                "Some used APIs have no matching catalog rule; they are listed as unresolved."
            )

        return UpgradeImpactReport(
            package_name=package_name,
            normalized_name=norm,
            current_version=current_version,
            target_version=target_version,
            analysis_source="deterministic",
            catalog_rules_applied=len(catalog),
            usage_sites=len(index.nodes),
            used_apis=used_apis,
            findings=findings,
            breaking_findings=breaking,
            unresolved_apis=unresolved_unique,
            unchanged_apis=sorted(set(unchanged)),
            affected_files=affected_files,
            official_references=refs,
            analysis_limitations=limitations,
            summary=summary,
            confidence=confidence,
        )

    def _findings_from_matches(
        self,
        *,
        package_name: str,
        current_version: str,
        target_version: str,
        matches: list[MatchedUsage],
    ) -> list[UpgradeImpactFinding]:
        by_api: dict[str, UpgradeImpactFinding] = {}
        for m in matches:
            rule = m.rule
            if rule.unchanged:
                continue
            key = f"{rule.symbol}:{rule.kind}"
            finding = by_api.get(key)
            evidence = ImpactEvidence(
                file_path=m.file_path,
                line=m.line,
                column=m.column,
                symbol=m.symbol,
                fully_qualified_name=m.fully_qualified_name,
                usage_kind=m.usage_kind,
                code_snippet=m.code_snippet,
                enclosing_function=m.enclosing_function,
                enclosing_class=m.enclosing_class,
            )
            is_breaking = (rule.kind in _BREAKING_KINDS) and not rule.unchanged
            if finding is None:
                by_api[key] = UpgradeImpactFinding(
                    dependency=package_name,
                    current_version=current_version,
                    target_version=target_version,
                    change_type=rule.kind,
                    affected_api=rule.symbol,
                    description=rule.description,
                    affected_files=[m.file_path],
                    evidence=[evidence],
                    confidence=float(m.match_confidence),
                    analysis_source="deterministic",
                    official_reference=rule.official_reference,
                    before=rule.before,
                    after=rule.after,
                    severity=rule.severity,
                    is_breaking=is_breaking,
                    auto_fixable=bool(rule.auto_fixable),
                )
            else:
                if m.file_path not in finding.affected_files:
                    finding.affected_files.append(m.file_path)
                finding.evidence.append(evidence)
                finding.confidence = max(finding.confidence, float(m.match_confidence))
        return list(by_api.values())
