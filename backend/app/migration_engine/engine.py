"""Universal Migration Intelligence Engine — orchestrates learn → match → report.

Two pipelines are strictly separated:
  A) Security Intelligence (OSV / CVE / GitHub advisories) — never used for migration.
  B) Migration Intelligence (official migration / upgrade / release / changelog docs)
     + structured rule catalog — deterministic matcher, no AI in matching.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.ai.analyzer import AIAnalyzer
from app.core.logging import get_logger
from app.migration_engine.cache import MigrationCache
from app.migration_engine.documentation_fetcher import (
    DocumentationFetcher,
    is_migration_source,
    is_security_url,
)
from app.migration_engine.models import (
    MigrationRuleBatch,
    MigrationRuleDTO,
    OfficialReference,
    PatchDTO,
    ScoringResult,
    UpgradeEngineReport,
)
from app.migration_engine.impact_explainer import ImpactExplainer
from app.migration_engine.patch_generator import PatchGenerator
from app.migration_engine.registry import LibraryRegistry
from app.migration_engine.release_fetcher import ReleaseFetcher
from app.migration_engine.rule_catalog import official_references_for, rules_for_upgrade
from app.migration_engine.rule_generator import RuleGenerator
from app.migration_engine.rule_matcher import RuleMatcher
from app.migration_engine.rule_store import RuleStore
from app.migration_engine.rule_validator import RuleValidator
from app.migration_engine.semantic_index import SemanticASTIndex
from app.scanners.normalize import normalize_package_name

logger = get_logger(__name__)

EFFORT_HOURS = {
    "trivial": 0.25,
    "low": 1.0,
    "medium": 3.0,
    "high": 8.0,
    "very_high": 16.0,
}


def _is_migration_rule(rule: MigrationRuleDTO) -> bool:
    if rule.kind == "security":
        return False
    ref = rule.official_reference or rule.source_url or ""
    if is_security_url(ref, rule.reference_title or ""):
        return False
    if rule.source_type and rule.source_type.lower() in {"security", "advisory", "cve", "osv"}:
        return False
    return True


def _merge_rules(
    catalog: list[MigrationRuleDTO],
    others: list[MigrationRuleDTO],
) -> list[MigrationRuleDTO]:
    """Catalog wins on (symbol, match_kind). Drop security-sourced others."""
    out: list[MigrationRuleDTO] = []
    seen: set[tuple[str, str]] = set()
    for r in catalog:
        key = ((r.symbol or "").lower(), (r.match_kind or r.kind or "").lower())
        seen.add(key)
        out.append(r)
    for r in others:
        if not _is_migration_rule(r):
            continue
        key = ((r.symbol or "").lower(), (r.match_kind or r.kind or "").lower())
        if key in seen:
            continue
        # Prefer catalog-style structured rules; skip vague keyword rules without match_kind
        # when catalog already covers this library upgrade.
        if catalog and not r.match_kind and not r.after and not r.unchanged:
            continue
        seen.add(key)
        out.append(r)
    return out


def _build_official_refs(
    package_name: str,
    rules: list[MigrationRuleDTO],
) -> tuple[list[str], list[OfficialReference]]:
    items: list[OfficialReference] = []
    seen: set[str] = set()

    def add(title: str, url: str, source_type: str = "docs") -> None:
        if not url or url in seen or is_security_url(url, title):
            return
        seen.add(url)
        items.append(OfficialReference(title=title, url=url, source_type=source_type))

    for ref in official_references_for(package_name):
        add(ref["title"], ref["url"], ref.get("source_type") or "docs")

    for r in rules:
        url = r.official_reference or r.source_url
        if not url:
            continue
        title = r.reference_title or None
        if not title:
            # Derive a short title from source_type — never spam "Official source"
            st = (r.source_type or "docs").replace("_", " ").title()
            title = f"{package_name} {st}"
        add(title, url, r.source_type or "docs")

    return [i.url for i in items], items


class MigrationEngine:
    """
    Core migration intelligence engine (Pipeline B).

    Matching and patches are deterministic (Semantic AST × structured rules).
    Security advisories are never used as migration sources.
    """

    def __init__(
        self,
        session: Session,
        ai: Optional[AIAnalyzer] = None,
        cache: Optional[MigrationCache] = None,
        *,
        allow_ai: bool = True,
    ) -> None:
        self.session = session
        self.cache = cache or MigrationCache()
        # Evaluation/Starter: allow_ai=False → DisabledAIAnalyzer (available=False), never None.
        from app.ai.analyzer import DisabledAIAnalyzer

        self.allow_ai = allow_ai
        if allow_ai:
            self.ai = ai if ai is not None else AIAnalyzer()
        else:
            self.ai = ai if isinstance(ai, DisabledAIAnalyzer) else DisabledAIAnalyzer()
        self.docs = DocumentationFetcher(self.cache)
        self.releases = ReleaseFetcher(self.cache)
        self.generator = RuleGenerator(self.ai, allow_ai=allow_ai)
        self.store = RuleStore(session, self.cache)
        self.matcher = RuleMatcher()
        self.validator = RuleValidator(session)
        self.registry = LibraryRegistry(session)
        self.explainer = ImpactExplainer(self.ai)
        self.patches = PatchGenerator()

    def ensure_rules(
        self,
        package_name: str,
        from_version: str,
        to_version: str,
        github_url: Optional[str] = None,
        force_refresh: bool = False,
    ) -> list[MigrationRuleDTO]:
        """
        Load structured migration rules for a version range.

        1) Always merge the deterministic rule catalog when the version range applies.
        2) Reuse stored migration rules (never security-sourced).
        3) If neither exists, learn from official migration docs only (not advisories).
        """
        catalog = rules_for_upgrade(package_name, from_version, to_version)
        existing = self.store.existing_rules(package_name, from_version, to_version)
        db_rules = [r for r in self.store.rules_as_dto(existing) if _is_migration_rule(r)]

        if catalog and not force_refresh:
            merged = _merge_rules(catalog, db_rules)
            logger.info(
                "rules_catalog_merged",
                package=normalize_package_name(package_name),
                catalog=len(catalog),
                db=len(db_rules),
                total=len(merged),
            )
            # SAVEPOINT: catalog persist must never poison the outer session.
            try:
                with self.session.begin_nested():
                    self._persist_catalog(
                        package_name, from_version, to_version, catalog, github_url
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("catalog_persist_failed", error=str(exc)[:500])
            return merged

        if db_rules and not force_refresh:
            logger.info(
                "rules_reused",
                package=normalize_package_name(package_name),
                count=len(db_rules),
            )
            return _merge_rules(catalog, db_rules)

        logger.info(
            "rules_learning",
            package=normalize_package_name(package_name),
            range=f"{from_version}->{to_version}",
        )

        pypi = self.docs.fetch_pypi_description(package_name)
        kb = self.store.get_or_create_kb(
            package_name,
            pypi_url=f"https://pypi.org/project/{normalize_package_name(package_name)}/",
            github_url=github_url or self.releases._github_from_pypi(pypi),
        )

        doc_sources = [
            s
            for s in self.docs.fetch_all_discovered(package_name, pypi)
            if is_migration_source(
                s.get("source_type") or "docs",
                s.get("url") or "",
                s.get("title") or "",
            )
        ]
        info = pypi.get("info") or {}
        if info.get("description"):
            doc_sources.append(
                {
                    "source_type": "pypi",
                    "url": f"https://pypi.org/project/{normalize_package_name(package_name)}/",
                    "title": "PyPI description",
                    "content": (info.get("description") or "")[:20000],
                    "content_hash": None,
                    "http_status": 200,
                }
            )

        release_bundle = self.releases.collect_for_range(
            package_name,
            from_version,
            to_version,
            github_url=kb.github_url,
            pypi_info=pypi,
        )
        # Strip security-only release notes from migration learning
        releases = [
            r
            for r in (release_bundle.get("releases") or [])
            if not is_security_url(r.get("url") or "", r.get("title") or "")
        ]

        self.store.store_documentation(kb, doc_sources)
        self.store.store_release_notes(package_name, releases)

        batch = self.generator.generate(
            library=package_name,
            from_version=from_version,
            to_version=to_version,
            documentation_excerpts=doc_sources,
            release_notes=releases,
        )

        validated_rules: list[MigrationRuleDTO] = []
        for rule in batch.rules:
            if not _is_migration_rule(rule):
                continue
            status, _errors = self.validator.validate_rule(rule)
            rule.validation_status = status
            if status != "rejected":
                validated_rules.append(rule)
        batch.rules = validated_rules

        stored = self.store.store_rules(batch, package_name, from_version, to_version, kb=kb)
        for orm in stored:
            dto = self.store._to_dto(orm)
            self.validator.apply_rule_validation_to_db(orm, dto)
        self.session.flush()

        learned = [r for r in self.store.rules_as_dto(stored) if _is_migration_rule(r)]
        return _merge_rules(catalog, learned)

    def _persist_catalog(
        self,
        package_name: str,
        from_version: str,
        to_version: str,
        catalog: list[MigrationRuleDTO],
        github_url: Optional[str],
    ) -> None:
        kb = self.store.get_or_create_kb(
            package_name,
            pypi_url=f"https://pypi.org/project/{normalize_package_name(package_name)}/",
            github_url=github_url,
        )
        batch = MigrationRuleBatch(rules=catalog, summary="Structured catalog rules")
        self.store.store_rules(batch, package_name, from_version, to_version, kb=kb)
        self.session.flush()

    def analyze_upgrade(
        self,
        *,
        package_name: str,
        from_version: str,
        to_version: str,
        usages: list[dict[str, Any]],
        github_url: Optional[str] = None,
        cve_hints: Optional[list[str]] = None,
        force_refresh_rules: bool = False,
    ) -> UpgradeEngineReport:
        # 1) Semantic AST Index — source of truth (deterministic)
        index = SemanticASTIndex.from_usage_dicts(usages).filter_package(package_name)

        # 2) Migration rules only (catalog + docs-learned). Never security.
        rules = self.ensure_rules(
            package_name,
            from_version,
            to_version,
            github_url=github_url,
            force_refresh=force_refresh_rules,
        )
        rules = [r for r in rules if _is_migration_rule(r)]

        # 3) Deterministic rule match — never uses AI
        matches = self.matcher.match_index(index, rules)

        from app.services.upgrade_helpers import build_ast_affected_files, rule_annotations_by_file

        affected_files = build_ast_affected_files(
            index.to_usage_dicts(),
            rule_annotations=rule_annotations_by_file(matches),
        )

        # 4) Real patches + classified findings (no fake diffs)
        patches, findings = self.patches.generate(matches)
        knowledge_available = bool(rules)
        # Unmatched usages: No changes only when rules exist; else Unknown
        unmatched = self.patches.classify_unmatched_usages(
            index.to_usage_dicts(),
            matches,
            knowledge_available=knowledge_available,
        )
        # Prefer matched findings; add unmatched only for symbols not already reported
        reported = {(f.file_path, f.line, (f.symbol or "").split(".")[-1].lower()) for f in findings}
        for u in unmatched:
            leaf = (u.symbol or "").split(".")[-1].lower()
            if (u.file_path, u.line, leaf) in reported:
                continue
            findings.append(u)

        patches = [self.validator.validate_patch(p) for p in patches]
        patches = [p for p in patches if p.validation_status != "rejected"]

        scoring = self._score(rules, matches, patches, findings, cve_hints or [])
        ref_urls, ref_items = _build_official_refs(package_name, rules)

        # 5) Explain / summarize after match (deterministic — never invents replacements)
        if not rules:
            # Package-level Unknown — never "No changes required" without knowledge
            from app.migration_engine.models import MigrationFinding

            package_unknown = MigrationFinding(
                status="unknown",
                file_path="(repository)",
                symbol=package_name,
                confidence=0.3,
                reason=(
                    "Unknown — no structured migration rules are available for this "
                    "library/version range. Insufficient deterministic knowledge."
                ),
                automatic=False,
            )
            # Keep per-usage Unknown rows; avoid duplicate package-level rows.
            findings = [package_unknown] + [
                f for f in findings if not (f.file_path == "(repository)" and f.status == "unknown")
            ]

        explanation = self.explainer.explain(
            package_name=package_name,
            from_version=from_version,
            to_version=to_version,
            rules=rules,
            matches=matches,
            scoring=scoring,
            index_size=len(index),
            official_references=ref_urls,
        )

        # Security improvements come ONLY from Pipeline A hints (cve_hints), never docs.
        security_improvements = [h for h in (cve_hints or [])][:15]
        performance_improvements = [
            r.description for r in rules if r.kind == "performance"
        ][:10]

        return UpgradeEngineReport(
            package_name=package_name,
            from_version=from_version,
            to_version=to_version,
            summary=explanation["summary"],
            scoring=scoring,
            matched_usages=matches,
            rules=rules,
            patches=patches,
            findings=findings,
            affected_files=affected_files,
            affected_symbols=index.symbols(),
            official_references=ref_urls,
            official_reference_items=ref_items,
            migration_plan=explanation["migration_plan"],
            security_improvements=security_improvements,
            performance_improvements=performance_improvements,
        )

    def _build_patches_from_rules(self, matches: list) -> list[PatchDTO]:
        """Compatibility wrapper — patches only when rule.after exists and applies."""
        patches, _findings = self.patches.generate(matches)
        return patches

    def _score(
        self,
        rules: list[MigrationRuleDTO],
        matches: list,
        patches: list[PatchDTO],
        findings: list | None = None,
        cve_hints: list[str] | None = None,
    ) -> ScoringResult:
        cve_hints = cve_hints or []
        findings = findings or []
        breaking = [
            m
            for m in matches
            if m.rule.kind in {"removed", "behavior_change", "signature_change"}
            and not m.rule.unchanged
        ]
        deprecated = [m for m in matches if m.rule.kind in {"deprecated", "renamed"}]
        auto = [p for p in patches if p.auto_fixable and p.validation_status == "validated"]
        manual = [f for f in findings if f.status == "manual_review_required"]

        readiness = 90.0
        readiness -= min(50.0, len(breaking) * 12)
        readiness -= min(20.0, len(deprecated) * 4)
        readiness += min(10.0, len(auto) * 2)
        readiness = max(5.0, min(100.0, readiness))

        risk = 100.0 - readiness + len(breaking) * 3
        risk = max(5.0, min(100.0, risk))

        hours = sum(
            EFFORT_HOURS.get(m.rule.estimated_effort, 3.0) * 0.35 for m in matches if not m.rule.unchanged
        ) or 0.5
        hours = round(max(0.5, hours), 1)

        order = ["trivial", "low", "medium", "high", "very_high"]
        difficulty = "low"
        for m in matches:
            if m.rule.unchanged:
                continue
            if m.rule.estimated_effort in order and order.index(m.rule.estimated_effort) > order.index(
                difficulty
            ):
                difficulty = m.rule.estimated_effort
        if not any(not m.rule.unchanged for m in matches):
            difficulty = "trivial"

        conf = 0.5
        if matches:
            conf = sum(m.match_confidence for m in matches) / len(matches)
        if rules:
            conf = (conf + sum(r.confidence for r in rules) / len(rules)) / 2

        # Security score from CVE pipeline only
        security = min(100.0, len(cve_hints) * 15)
        performance = min(100.0, sum(1 for r in rules if r.kind == "performance") * 20)
        debt = min(100.0, len(deprecated) * 10 + len(auto) * 5)

        return ScoringResult(
            readiness_score=round(readiness, 1),
            risk_score=round(risk, 1),
            confidence=round(min(1.0, conf), 3),
            migration_difficulty=difficulty,
            migration_time_hours=hours,
            security_improvement=round(security, 1),
            performance_improvement=round(performance, 1),
            technical_debt_reduction=round(debt, 1),
            auto_fix_count=len(auto),
            manual_fix_count=len(manual),
            breakdown={
                "breaking_matches": len(breaking),
                "deprecated_matches": len(deprecated),
                "rules_total": len(rules),
                "usage_matches": len(matches),
                "findings_auto": sum(1 for f in findings if f.status == "automatic_migration"),
                "findings_none": sum(1 for f in findings if f.status == "no_migration_required"),
                "findings_manual": len(manual),
                "findings_unknown": sum(1 for f in findings if f.status == "unknown"),
                "knowledge_available": bool(rules),
            },
        )
