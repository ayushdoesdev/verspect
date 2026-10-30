"""Deterministic per-category upgrade analysis.

Uses catalog rules (Python), repository usage, version comparison, and
generalized changelog extraction. Never treats a major bump as BREAKING.
"""

from __future__ import annotations

from typing import Any, Optional

from app.scanners.pypi import compare_versions
from app.services.upgrade_impact import UpgradeImpactReport
from app.services.upgrade_intelligence.categories import CATEGORY_TITLES, CategoryId
from app.services.upgrade_intelligence.models import (
    AffectedLocation,
    CategoryFinding,
    CategoryResult,
    EvidenceBundle,
    EvidenceItem,
    IntelligenceReport,
)

_KIND_TO_CATEGORY: dict[str, CategoryId] = {
    "removed": "removed_apis",
    "renamed": "renamed_apis",
    "signature_change": "changed_signatures",
    "behavior_change": "changed_defaults",
    "deprecated": "deprecated_functionality",
    "import_path_change": "changed_modules",
    "type_change": "changed_types",
    "configuration": "changed_configuration",
    "breaking": "breaking_changes",
    "security": "security_relevant_changes",
}

_BREAKING_KINDS = {
    "removed",
    "renamed",
    "signature_change",
    "behavior_change",
    "import_path_change",
    "breaking",
}


def _leaf(name: str) -> str:
    token = (name or "").strip()
    if not token:
        return ""
    token = token.replace("::", ".").replace("/", ".")
    return token.split(".")[-1].lower().lstrip(".")


class DeterministicCategoryAnalyzer:
    def analyze(
        self,
        *,
        package_name: str,
        ecosystem: str,
        current_version: str,
        target_version: str,
        usages: list[dict[str, Any]],
        impact: Optional[UpgradeImpactReport],
        evidence: EvidenceBundle,
        latest_version: Optional[str] = None,
        graph_neighbors: Optional[list[str]] = None,
        lockfile_note: Optional[str] = None,
    ) -> IntelligenceReport:
        report = IntelligenceReport(
            package_name=package_name,
            ecosystem=ecosystem,
            from_version=current_version,
            to_version=target_version,
            catalog_rules_applied=impact.catalog_rules_applied if impact else 0,
            usage_sites=len(usages),
            evidence=list(evidence.items),
            degradation=list(evidence.degradation),
        )
        usage_index = self._index_usages(usages)
        catalog_findings = self._catalog_findings(impact)
        has_catalog = bool(impact and impact.catalog_rules_applied)
        changelog_matches = self._match_changelog(
            evidence.extracted_changes, usage_index, package_name
        )

        locations = self._usage_locations(usages)
        report.affected_files = locations

        self._fill_what_changed(report, impact, evidence, catalog_findings, changelog_matches, has_catalog)
        self._fill_api_change_categories(report, catalog_findings, changelog_matches, has_catalog, evidence)
        self._fill_security(report, evidence, changelog_matches)
        self._fill_usage_categories(report, usages, locations, catalog_findings, changelog_matches, has_catalog)
        self._fill_required_changes(report, catalog_findings, changelog_matches, has_catalog)
        self._fill_migration(report, impact, catalog_findings, changelog_matches, has_catalog)
        self._fill_affected_deps(report, graph_neighbors, lockfile_note)
        self._fill_meta(report, impact, evidence, latest_version, catalog_findings, changelog_matches)
        report.ensure_all_categories()
        return report

    def _index_usages(self, usages: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        index: dict[str, list[dict[str, Any]]] = {}
        for u in usages:
            keys = {
                _leaf(str(u.get("symbol") or "")),
                _leaf(str(u.get("fully_qualified_name") or "")),
                _leaf(str(u.get("module_path") or "")),
            }
            for key in keys:
                if not key:
                    continue
                index.setdefault(key, []).append(u)
        return index

    def _usage_locations(self, usages: list[dict[str, Any]]) -> list[AffectedLocation]:
        out: list[AffectedLocation] = []
        seen: set[tuple[str, Optional[int], str]] = set()
        for u in usages:
            path = str(u.get("file_path") or "")
            if not path:
                continue
            line = u.get("line")
            api = str(u.get("fully_qualified_name") or u.get("symbol") or "")
            key = (path, int(line) if line is not None else None, api)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                AffectedLocation(
                    file=path,
                    line=int(line) if line is not None else None,
                    column=u.get("column"),
                    api=api or None,
                    reason="Verified repository usage of this dependency.",
                    confidence=0.95,
                    analysis_method="deterministic",
                    usage_kind="verified",
                    snippet=(u.get("code_snippet") or None),
                )
            )
        return out

    def _catalog_findings(self, impact: Optional[UpgradeImpactReport]) -> list[CategoryFinding]:
        if impact is None:
            return []
        out: list[CategoryFinding] = []
        for f in impact.findings:
            cat = _KIND_TO_CATEGORY.get(f.change_type, "changed_apis")
            locs = [
                AffectedLocation(
                    file=e.file_path,
                    line=e.line,
                    column=e.column,
                    api=e.fully_qualified_name or e.symbol or f.affected_api,
                    reason=f.description,
                    confidence=f.confidence,
                    analysis_method="deterministic",
                    usage_kind="verified",
                    snippet=e.code_snippet,
                )
                for e in f.evidence
                if e.file_path
            ]
            out.append(
                CategoryFinding(
                    category=cat,
                    finding=f.affected_api,
                    explanation=f.description,
                    affected_files=locs,
                    affected_lines=[e.line for e in f.evidence if e.line is not None],
                    required_change=(
                        f"{locs[0].file}:{locs[0].line} uses {f.affected_api}. "
                        f"{f.description}"
                        + (f" Replace with {f.after}." if f.after else "")
                    )
                    if locs
                    else f.description,
                    confidence=f.confidence,
                    evidence=[
                        EvidenceItem(
                            kind="catalog_rule",
                            text=f.description,
                            source=f.official_reference,
                            reliability="high",
                            untrusted=False,
                        )
                    ],
                    source=f.official_reference,
                    analysis_method="deterministic",
                    status="verified" if f.evidence else "likely",
                )
            )
        return out

    def _match_changelog(
        self,
        extracted: list[dict[str, Any]],
        usage_index: dict[str, list[dict[str, Any]]],
        package_name: str = "",
    ) -> list[CategoryFinding]:
        package_leaves = {
            _leaf(package_name),
            _leaf(package_name.split("/")[-1] if "/" in package_name else ""),
            _leaf(package_name.split(":")[-1] if ":" in package_name else ""),
        }
        package_leaves.discard("")
        findings: list[CategoryFinding] = []
        for change in extracted:
            ident = str(change.get("identifier") or "")
            kind = str(change.get("kind") or "changed_apis")
            cat = _KIND_TO_CATEGORY.get(kind, "changed_apis")
            ident_leaf = _leaf(ident)
            usages = usage_index.get(ident_leaf, [])
            if ident_leaf in package_leaves:
                # A changelog mention of the package name is not an API usage match.
                usages = []
            locs = [
                AffectedLocation(
                    file=str(u.get("file_path") or ""),
                    line=u.get("line"),
                    api=str(u.get("fully_qualified_name") or u.get("symbol") or ident),
                    reason=f"Repository uses `{ident}`, which release notes mention as {kind}.",
                    confidence=0.78 if usages else 0.4,
                    analysis_method="deterministic",
                    usage_kind="verified" if usages else "probable",
                    snippet=u.get("code_snippet"),
                )
                for u in usages
                if u.get("file_path")
            ]
            used = bool(usages)
            findings.append(
                CategoryFinding(
                    category=cat,
                    finding=ident,
                    explanation=(change.get("line") or f"{kind}: {ident}")[:500],
                    affected_files=locs,
                    affected_lines=[loc.line for loc in locs if loc.line is not None],
                    required_change=(
                        f"{locs[0].file}:{locs[0].line} uses {ident}. Release notes report a {kind} — review and migrate this call."
                        if locs
                        else None
                    ),
                    confidence=0.78 if used else 0.45,
                    evidence=[
                        EvidenceItem(
                            kind="changelog",
                            text=str(change.get("line") or ident),
                            source=str(change.get("source") or ""),
                            reliability="medium",
                            untrusted=True,
                        )
                    ],
                    source=str(change.get("source") or ""),
                    analysis_method="deterministic",
                    status="likely" if used else "possible",
                )
            )
        return findings

    def _set(
        self,
        report: IntelligenceReport,
        category_id: CategoryId,
        *,
        completeness: str,
        answer: str,
        findings: Optional[list[CategoryFinding]] = None,
        gaps: Optional[list[str]] = None,
        claim_status: str = "unresolved",
    ) -> CategoryResult:
        result = CategoryResult(
            id=category_id,
            title=CATEGORY_TITLES[category_id],
            deterministic_completeness=completeness,  # type: ignore[arg-type]
            completeness=completeness,  # type: ignore[arg-type]
            analysis_method="deterministic",
            claim_status=claim_status,  # type: ignore[arg-type]
            answer=answer,
            findings=findings or [],
            gaps=gaps or [],
        )
        report.categories[category_id] = result
        return result

    def _fill_what_changed(
        self,
        report: IntelligenceReport,
        impact: Optional[UpgradeImpactReport],
        evidence: EvidenceBundle,
        catalog: list[CategoryFinding],
        changelog: list[CategoryFinding],
        has_catalog: bool,
    ) -> None:
        bits: list[str] = []
        try:
            cmp_ = compare_versions(report.from_version, report.to_version)
            if cmp_.get("major_behind"):
                bits.append(
                    f"Major version delta ({report.from_version} → {report.to_version}). "
                    "A major bump is not by itself a verified breaking change."
                )
            elif cmp_.get("minor_behind"):
                bits.append(f"Minor version delta ({report.from_version} → {report.to_version}).")
            elif cmp_.get("patch_behind") or cmp_.get("is_outdated"):
                bits.append(f"Patch/version delta ({report.from_version} → {report.to_version}).")
            else:
                bits.append(f"Version range {report.from_version} → {report.to_version}.")
        except Exception:  # noqa: BLE001
            bits.append(f"Version range {report.from_version} → {report.to_version} (unparsed).")
            report.degradation.append("invalid_target_version")

        findings = catalog + changelog
        if has_catalog:
            bits.append(
                f"{impact.catalog_rules_applied if impact else 0} catalog rule(s) applied; "
                f"{len(catalog)} matched repository usage."
            )
        if changelog:
            bits.append(f"{len(changelog)} documented change(s) extracted from release notes.")
        if evidence.release_notes:
            bits.append("Release notes/changelog excerpts were collected.")
        elif "package_registry_unavailable" in evidence.degradation:
            bits.append("Package registry was unavailable; change list is incomplete.")
        completeness = "complete" if (catalog or changelog or has_catalog or evidence.release_notes) else (
            "partial" if bits else "empty"
        )
        if not catalog and not changelog and not has_catalog:
            gaps = ["No structured API-level change list from catalog or changelog extraction."]
            completeness = "partial" if evidence.release_notes or bits else "empty"
        else:
            gaps = []
        self._set(
            report,
            "what_changed",
            completeness=completeness,
            answer=" ".join(bits),
            findings=findings[:40],
            gaps=gaps,
            claim_status="verified" if catalog or has_catalog else ("likely" if changelog else "possible"),
        )

    def _fill_api_change_categories(
        self,
        report: IntelligenceReport,
        catalog: list[CategoryFinding],
        changelog: list[CategoryFinding],
        has_catalog: bool,
        evidence: EvidenceBundle,
    ) -> None:
        by_cat: dict[str, list[CategoryFinding]] = {}
        for f in catalog + changelog:
            by_cat.setdefault(f.category, []).append(f)

        breaking_findings = [
            f
            for f in catalog + changelog
            if f.category in {"removed_apis", "renamed_apis", "changed_signatures", "changed_modules"}
            or (f.category == "changed_defaults" and f.status in {"verified", "likely"})
        ]
        # Also include explicit breaking changelog hits used in the repo
        for f in changelog:
            if any(e.kind == "changelog" for e in f.evidence) and f.affected_files:
                if f.category in {"breaking_changes", "removed_apis", "renamed_apis", "changed_signatures"}:
                    if f not in breaking_findings:
                        breaking_findings.append(f)

        has_docs = bool(evidence.release_notes or evidence.extracted_changes)
        if has_catalog:
            completeness = "complete"
            status = "verified"
            answer = (
                f"{len(breaking_findings)} breaking API match(es) against repository usage."
                if breaking_findings
                else "Deterministic catalog rules exist for this range and none matched repository usage as breaking."
            )
            gaps = []
        elif breaking_findings:
            # Usage-matched documentation is enough for this category — do not send it to AI.
            completeness = "complete"
            status = "likely"
            answer = (
                f"{len(breaking_findings)} documented change(s) match repository usage. "
                "Not treated as verified breaking without a catalog rule or stronger evidence."
            )
            gaps = ["Changelog extraction is heuristic; confirm against official migration docs."]
        elif by_cat:
            completeness = "complete" if has_docs else "partial"
            status = "possible"
            answer = "Documented API changes were extracted but none matched verified repository usage."
            gaps = ["No usage match for documented identifiers."]
        elif has_docs:
            completeness = "complete"
            status = "possible"
            answer = (
                "Collected release notes did not identify breaking API changes affecting indexed usage."
            )
            gaps = []
        else:
            completeness = "empty"
            status = "unresolved"
            answer = "No deterministic breaking-change evidence for this version range."
            gaps = ["No catalog rules and no changelog identifiers to classify breaking changes."]

        self._set(
            report,
            "breaking_changes",
            completeness=completeness,
            answer=answer,
            findings=breaking_findings,
            gaps=gaps,
            claim_status=status,
        )

        for cid in (
            "removed_apis",
            "renamed_apis",
            "changed_apis",
            "changed_signatures",
            "changed_types",
            "changed_modules",
            "changed_configuration",
            "changed_defaults",
            "deprecated_functionality",
        ):
            rows = by_cat.get(cid, [])
            if cid == "changed_apis":
                rows = rows or [
                    f
                    for f in catalog + changelog
                    if f.category in {"removed_apis", "renamed_apis", "changed_signatures", "changed_types"}
                ]
            if rows:
                used = [f for f in rows if f.affected_files]
                self._set(
                    report,
                    cid,  # type: ignore[arg-type]
                    completeness="complete",
                    answer=(
                        f"{len(rows)} {CATEGORY_TITLES[cid].lower()} finding(s); "
                        f"{len(used)} used in this repository."
                    ),
                    findings=rows,
                    gaps=[] if has_catalog else ["Derived from documentation extraction, not a package catalog."],
                    claim_status="verified" if has_catalog and used else ("likely" if used else "possible"),
                )
            else:
                if has_catalog or has_docs:
                    self._set(
                        report,
                        cid,  # type: ignore[arg-type]
                        completeness="complete",
                        answer=(
                            f"No {CATEGORY_TITLES[cid].lower()} matched catalog rules for used APIs."
                            if has_catalog
                            else f"Collected documentation did not mention {CATEGORY_TITLES[cid].lower()}."
                        ),
                        findings=[],
                        claim_status="verified" if has_catalog else "possible",
                    )
                else:
                    self._set(
                        report,
                        cid,  # type: ignore[arg-type]
                        completeness="empty",
                        answer=f"No deterministic {CATEGORY_TITLES[cid].lower()} evidence.",
                        findings=[],
                        gaps=["Needs changelog/AI investigation."],
                        claim_status="unresolved",
                    )

    def _fill_security(
        self,
        report: IntelligenceReport,
        evidence: EvidenceBundle,
        changelog: list[CategoryFinding],
    ) -> None:
        hints = list(evidence.security_hints)
        findings = [
            CategoryFinding(
                category="security_relevant_changes",
                finding=h[:200],
                explanation=h,
                confidence=0.7,
                evidence=[
                    EvidenceItem(
                        kind="security_advisory",
                        text=h,
                        reliability="high",
                        untrusted=True,
                    )
                ],
                analysis_method="deterministic",
                status="likely",
            )
            for h in hints[:20]
        ]
        for f in changelog:
            if f.category == "security_relevant_changes":
                findings.append(f)
        if findings:
            self._set(
                report,
                "security_relevant_changes",
                completeness="complete",
                answer=f"{len(findings)} security-relevant note(s) associated with this upgrade range.",
                findings=findings,
                gaps=["Confirm whether each advisory is fixed by the target version."],
                claim_status="likely",
            )
        elif evidence.release_notes or evidence.extracted_changes:
            self._set(
                report,
                "security_relevant_changes",
                completeness="complete",
                answer="Collected release notes did not include security advisories for this range.",
                findings=[],
                claim_status="possible",
            )
        else:
            self._set(
                report,
                "security_relevant_changes",
                completeness="complete",
                answer="No security advisories were attached to this upgrade analysis.",
                findings=[],
                claim_status="possible",
            )

    def _fill_usage_categories(
        self,
        report: IntelligenceReport,
        usages: list[dict[str, Any]],
        locations: list[AffectedLocation],
        catalog: list[CategoryFinding],
        changelog: list[CategoryFinding],
        has_catalog: bool,
    ) -> None:
        used_apis = sorted(
            {
                str(u.get("fully_qualified_name") or u.get("symbol") or "").strip()
                for u in usages
                if (u.get("fully_qualified_name") or u.get("symbol"))
            }
        )
        impacted = {
            f.finding
            for f in catalog + changelog
            if f.affected_files and f.status in {"verified", "likely"}
        }
        affected_used = [a for a in used_apis if _leaf(a) in {_leaf(x) for x in impacted}]
        if usages:
            self._set(
                report,
                "affected_apis_used",
                completeness="complete",
                answer=(
                    f"This repository uses {len(used_apis)} API(s) of {report.package_name}. "
                    + (
                        f"{len(affected_used)} overlap documented/catalog changes."
                        if affected_used
                        else "None of the used APIs matched a documented change identifier."
                    )
                ),
                findings=[
                    CategoryFinding(
                        category="affected_apis_used",
                        finding=api,
                        explanation="Verified usage site.",
                        affected_files=[loc for loc in locations if loc.api == api][:8],
                        confidence=0.95,
                        analysis_method="deterministic",
                        status="verified",
                    )
                    for api in (affected_used or used_apis[:30])
                ],
                gaps=(
                    ["Documented changes may mention APIs not present in the usage index."]
                    if changelog and not catalog
                    else []
                ),
                claim_status="verified",
            )
            self._set(
                report,
                "affected_files",
                completeness="complete",
                answer=f"{len({loc.file for loc in locations})} file(s) contain verified usage.",
                findings=[
                    CategoryFinding(
                        category="affected_files",
                        finding=loc.file,
                        explanation=loc.reason,
                        affected_files=[loc],
                        affected_lines=[loc.line] if loc.line is not None else [],
                        confidence=loc.confidence,
                        analysis_method="deterministic",
                        status="verified",
                    )
                    for loc in locations[:80]
                ],
                claim_status="verified",
            )
            lined = [loc for loc in locations if loc.line is not None]
            self._set(
                report,
                "affected_lines",
                completeness="complete" if lined else "partial",
                answer=(
                    f"{len(lined)} usage site(s) include line numbers."
                    if lined
                    else "Usage was found but line numbers were not recorded."
                ),
                findings=[
                    CategoryFinding(
                        category="affected_lines",
                        finding=f"{loc.file}:{loc.line}",
                        explanation=loc.reason,
                        affected_files=[loc],
                        affected_lines=[loc.line] if loc.line is not None else [],
                        required_change=None,
                        confidence=0.95,
                        analysis_method="deterministic",
                        status="verified",
                    )
                    for loc in lined[:80]
                ],
                claim_status="verified" if lined else "possible",
            )
            self._set(
                report,
                "why_file_affected",
                completeness="complete",
                answer="Each listed file imports or calls this dependency.",
                findings=[
                    CategoryFinding(
                        category="why_file_affected",
                        finding=loc.file,
                        explanation=(
                            f"`{loc.file}`"
                            + (f":{loc.line}" if loc.line is not None else "")
                            + f" uses `{loc.api or report.package_name}`."
                        ),
                        affected_files=[loc],
                        confidence=0.95,
                        analysis_method="deterministic",
                        status="verified",
                    )
                    for loc in locations[:80]
                ],
                claim_status="verified",
            )
        else:
            for cid in ("affected_apis_used", "affected_files", "affected_lines", "why_file_affected"):
                self._set(
                    report,
                    cid,  # type: ignore[arg-type]
                    completeness="complete",
                    answer="No repository usage of this dependency was indexed.",
                    findings=[],
                    claim_status="verified",
                )

    def _fill_required_changes(
        self,
        report: IntelligenceReport,
        catalog: list[CategoryFinding],
        changelog: list[CategoryFinding],
        has_catalog: bool,
    ) -> None:
        required = [f for f in catalog if f.required_change]
        likely = [f for f in changelog if f.required_change and f.affected_files]
        rows = required or likely
        report.required_changes = rows
        if required:
            self._set(
                report,
                "required_code_changes",
                completeness="complete",
                answer=f"{len(required)} repository-specific code change(s) from catalog matches.",
                findings=required,
                claim_status="verified",
            )
        elif likely:
            self._set(
                report,
                "required_code_changes",
                completeness="complete",
                answer=f"{len(likely)} usage site(s) overlap documented changes and need review.",
                findings=likely,
                gaps=["Replacement APIs are not invented when docs do not state them."],
                claim_status="likely",
            )
        elif has_catalog:
            self._set(
                report,
                "required_code_changes",
                completeness="complete",
                answer="Catalog rules exist; no code changes required for indexed usage.",
                claim_status="verified",
            )
        elif report.usage_sites:
            self._set(
                report,
                "required_code_changes",
                completeness="empty",
                answer="Usage exists but no deterministic migration edit was established.",
                gaps=["Needs documentation-backed or AI-derived replacements."],
                claim_status="unresolved",
            )
        else:
            self._set(
                report,
                "required_code_changes",
                completeness="complete",
                answer="No repository usage — no code changes required in this repo.",
                claim_status="verified",
            )

        config = [f for f in catalog + changelog if f.category == "changed_configuration"]
        if config:
            used = [f for f in config if f.affected_files]
            self._set(
                report,
                "required_configuration_changes",
                completeness="partial" if not has_catalog else "complete",
                answer=(
                    f"{len(config)} configuration change(s) documented"
                    + (f"; {len(used)} referenced in this repository." if used else ".")
                ),
                findings=config,
                claim_status="likely" if used else "possible",
            )
        else:
            self._set(
                report,
                "required_configuration_changes",
                completeness="empty" if not has_catalog else "complete",
                answer="No deterministic configuration-change evidence.",
                gaps=[] if has_catalog else ["Needs docs/AI for config keys."],
                claim_status="verified" if has_catalog else "unresolved",
            )

    def _fill_migration(
        self,
        report: IntelligenceReport,
        impact: Optional[UpgradeImpactReport],
        catalog: list[CategoryFinding],
        changelog: list[CategoryFinding],
        has_catalog: bool,
    ) -> None:
        rules: list[dict[str, Any]] = []
        for f in catalog:
            rules.append(
                {
                    "symbol": f.finding,
                    "kind": f.category,
                    "description": f.explanation,
                    "reason": f.explanation,
                    "severity": "high" if f.status == "verified" else "medium",
                    "confidence": f.confidence,
                    "auto_fixable": False,
                    "official_reference": f.source,
                    "analysis_source": "deterministic",
                    "evidence": [e.model_dump() for e in f.evidence],
                    "required_change": f.required_change,
                }
            )
        for f in changelog:
            if any(r["symbol"] == f.finding and r["kind"] == f.category for r in rules):
                continue
            rules.append(
                {
                    "symbol": f.finding,
                    "kind": f.category,
                    "description": f.explanation,
                    "reason": f.explanation,
                    "severity": "medium",
                    "confidence": f.confidence,
                    "auto_fixable": False,
                    "official_reference": f.source,
                    "analysis_source": "deterministic",
                    "evidence": [e.model_dump() for e in f.evidence],
                    "required_change": f.required_change,
                }
            )
        report.migration_rules = rules
        if rules:
            self._set(
                report,
                "migration_rules",
                completeness="complete",
                answer=f"{len(rules)} migration rule(s) derived from catalog and/or documentation.",
                findings=catalog + [f for f in changelog if f.required_change],
                claim_status="verified" if has_catalog else "likely",
            )
            steps = []
            for f in catalog + changelog:
                if f.required_change:
                    steps.append(
                        CategoryFinding(
                            category="migration_steps",
                            finding=f.finding,
                            explanation=f.required_change,
                            affected_files=f.affected_files,
                            required_change=f.required_change,
                            confidence=f.confidence,
                            evidence=f.evidence,
                            source=f.source,
                            analysis_method="deterministic",
                            status=f.status,
                        )
                    )
            if steps:
                self._set(
                    report,
                    "migration_steps",
                    completeness="complete",
                    answer="Repository-specific steps from matched usage.",
                    findings=steps,
                    claim_status="verified" if has_catalog else "likely",
                )
            elif report.usage_sites and not has_catalog:
                self._set(
                    report,
                    "migration_steps",
                    completeness="empty",
                    answer="Documented changes exist, but no file:line migration step was established for indexed usage.",
                    gaps=["AI may derive repository-specific steps from official notes when the plan includes AI."],
                    claim_status="unresolved",
                )
            else:
                self._set(
                    report,
                    "migration_steps",
                    completeness="complete",
                    answer="No repository-specific migration steps required for indexed usage.",
                    claim_status="verified" if has_catalog else "possible",
                )
        elif has_catalog:
            self._set(
                report,
                "migration_rules",
                completeness="complete",
                answer="Catalog rules exist for this range; none required a repository-specific migration edit for indexed usage.",
                claim_status="verified",
            )
            self._set(
                report,
                "migration_steps",
                completeness="complete",
                answer="No repository-specific migration steps required for indexed usage.",
                claim_status="verified",
            )
        else:
            self._set(
                report,
                "migration_rules",
                completeness="empty",
                answer="No deterministic migration rules for this range.",
                gaps=["AI may derive guidance from official notes when the plan includes AI."],
                claim_status="unresolved",
            )
            self._set(
                report,
                "migration_steps",
                completeness="empty" if report.usage_sites else "complete",
                answer=(
                    "No deterministic migration steps."
                    if report.usage_sites
                    else "No repository usage — no migration steps required."
                ),
                claim_status="unresolved" if report.usage_sites else "verified",
            )

    def _fill_affected_deps(
        self,
        report: IntelligenceReport,
        graph_neighbors: Optional[list[str]],
        lockfile_note: Optional[str],
    ) -> None:
        neighbors = [n for n in (graph_neighbors or []) if n]
        findings = [
            CategoryFinding(
                category="affected_dependencies",
                finding=n,
                explanation="Appears as a graph neighbor of the upgraded package.",
                confidence=0.7,
                analysis_method="deterministic",
                status="possible",
            )
            for n in neighbors[:30]
        ]
        bits = []
        if neighbors:
            bits.append(f"{len(neighbors)} graph neighbor(s) may also need review.")
        if lockfile_note:
            bits.append(lockfile_note)
        if bits:
            self._set(
                report,
                "affected_dependencies",
                completeness="partial",
                answer=" ".join(bits),
                findings=findings,
                gaps=["Transitive impact is inferred from the stored graph, not a resolver simulation."],
                claim_status="possible",
            )
        else:
            self._set(
                report,
                "affected_dependencies",
                completeness="complete",
                answer="No dependency-graph neighbors were supplied for this package. None identified from available inputs.",
                claim_status="possible",
            )

    def _fill_meta(
        self,
        report: IntelligenceReport,
        impact: Optional[UpgradeImpactReport],
        evidence: EvidenceBundle,
        latest_version: Optional[str],
        catalog: list[CategoryFinding],
        changelog: list[CategoryFinding],
    ) -> None:
        sources: list[dict[str, str]] = []
        for doc in evidence.documentation_urls:
            sources.append(
                {"label": doc.get("label") or doc.get("type") or "docs", "url": doc.get("url") or ""}
            )
        if evidence.github_repo_url:
            sources.append({"label": "repository", "url": evidence.github_repo_url})
        if evidence.registry.get("home_page"):
            sources.append({"label": "homepage", "url": str(evidence.registry["home_page"])})
        for rel in evidence.github_releases[:8]:
            if rel.get("url"):
                sources.append({"label": rel.get("tag") or "release", "url": str(rel["url"])})
        report.sources = [s for s in sources if s.get("url")]

        self._set(
            report,
            "sources",
            completeness="complete",
            answer=(
                f"{len(report.sources)} source URL(s) collected."
                if report.sources
                else "No official source URLs were collected from registry or documentation metadata."
            ),
            findings=[
                CategoryFinding(
                    category="sources",
                    finding=s["label"],
                    explanation=s["url"],
                    source=s["url"],
                    confidence=0.9,
                    analysis_method="deterministic",
                    status="verified",
                )
                for s in report.sources
            ],
            claim_status="verified" if report.sources else "unresolved",
        )
        self._set(
            report,
            "evidence",
            completeness="complete" if evidence.items or catalog or evidence.release_notes else "complete",
            answer=(
                f"{len(evidence.items)} evidence item(s) recorded with source and reliability."
                if evidence.items
                else "No additional evidence items were attached beyond version and usage inputs."
            ),
            findings=[
                CategoryFinding(
                    category="evidence",
                    finding=e.kind,
                    explanation=e.text[:400],
                    source=e.source,
                    confidence=0.8 if e.reliability == "high" else 0.55,
                    evidence=[e],
                    analysis_method="deterministic",
                    status="verified" if e.reliability == "high" else "likely",
                )
                for e in evidence.items[:40]
            ],
            claim_status="verified" if evidence.items or catalog else "possible",
        )

        target = report.to_version or latest_version or evidence.latest_version
        rec = target or report.to_version
        self._set(
            report,
            "recommended_target_version",
            completeness="complete" if rec else "empty",
            answer=(
                f"Requested target is {rec}."
                + (
                    f" Registry latest is {evidence.latest_version}."
                    if evidence.latest_version and evidence.latest_version != rec
                    else ""
                )
            ),
            findings=[
                CategoryFinding(
                    category="recommended_target_version",
                    finding=str(rec),
                    explanation="Target version supplied by the simulator (not invented).",
                    confidence=0.95,
                    analysis_method="deterministic",
                    status="verified",
                )
            ]
            if rec
            else [],
            claim_status="verified" if rec else "unresolved",
        )

        used_breaking = [
            f
            for f in catalog
            if f.affected_files and f.category in {"removed_apis", "renamed_apis", "changed_signatures", "changed_modules"}
        ]
        likely_breaking = [
            f
            for f in changelog
            if f.affected_files
            and f.category in {"removed_apis", "renamed_apis", "changed_signatures", "changed_modules", "breaking_changes"}
        ]
        major = False
        try:
            major = bool(compare_versions(report.from_version, report.to_version).get("major_behind"))
        except Exception:  # noqa: BLE001
            major = False

        if used_breaking:
            classification = "breaking"
        elif likely_breaking:
            classification = "potentially_breaking"
        elif report.catalog_rules_applied and not used_breaking:
            classification = "low_risk" if report.usage_sites else "safe"
        elif report.usage_sites == 0:
            classification = "safe"
        elif changelog and not likely_breaking:
            classification = "low_risk"
        elif major and report.usage_sites:
            classification = "unresolved"
        else:
            classification = "unresolved"
        report.breaking_classification = classification  # type: ignore[assignment]

        risk_answer = {
            "breaking": "Verified breaking API usage in this repository.",
            "potentially_breaking": "Documented changes overlap repository usage but are not catalog-verified.",
            "low_risk": "Usage exists; no verified breaking matches.",
            "safe": "No repository usage of this dependency, or catalog shows no breaking matches.",
            "unresolved": "Insufficient deterministic evidence to classify risk. A major version alone is not breaking.",
        }[classification]
        self._set(
            report,
            "upgrade_risk",
            completeness="complete" if classification != "unresolved" else "empty",
            answer=risk_answer,
            findings=used_breaking or likely_breaking,
            gaps=[] if classification != "unresolved" else ["Needs AI or additional documentation."],
            claim_status="verified" if classification in {"breaking", "safe", "low_risk"} and (catalog or report.catalog_rules_applied) else (
                "likely" if classification != "unresolved" else "unresolved"
            ),
        )

        conf = 0.35
        if catalog:
            conf = max((f.confidence for f in catalog), default=0.85)
        elif report.catalog_rules_applied:
            conf = 0.8
        elif likely_breaking:
            conf = 0.62
        elif report.usage_sites and evidence.release_notes:
            conf = 0.48
        elif report.usage_sites:
            conf = 0.4
        report.confidence = conf
        self._set(
            report,
            "confidence",
            completeness="complete",
            answer=f"Deterministic confidence {round(conf * 100)}% based on catalog, usage, and documentation coverage.",
            claim_status="verified",
        )

        migration_needed = bool(used_breaking or likely_breaking or (catalog and any(f.required_change for f in catalog)))
        self._set(
            report,
            "migration_required",
            completeness="complete" if classification != "unresolved" or not report.usage_sites else "partial",
            answer="Yes — repository usage overlaps known changes." if migration_needed else (
                "No deterministic migration requirement." if classification in {"safe", "low_risk"} else "Unknown until remaining gaps are filled."
            ),
            claim_status="verified" if classification != "unresolved" else "unresolved",
        )
        appears_safe = classification in {"safe", "low_risk"}
        self._set(
            report,
            "upgrade_appears_safe",
            completeness="complete" if classification != "unresolved" else "empty",
            answer="Yes" if appears_safe else ("No" if classification == "breaking" else "Not established."),
            claim_status="verified" if classification != "unresolved" else "unresolved",
        )
        self._set(
            report,
            "upgrade_potentially_breaking",
            completeness="complete" if classification != "unresolved" else "empty",
            answer="Yes" if classification in {"potentially_breaking", "breaking"} else "No",
            claim_status="verified" if classification != "unresolved" else "unresolved",
        )
        self._set(
            report,
            "upgrade_verified_breaking",
            completeness="complete" if used_breaking or (catalog and classification != "unresolved") else (
                "empty" if classification == "unresolved" else "complete"
            ),
            answer="Yes" if classification == "breaking" and used_breaking else "No",
            claim_status="verified" if used_breaking or report.catalog_rules_applied else (
                "unresolved" if classification == "unresolved" else "likely"
            ),
        )

        if impact and impact.summary:
            report.summary = impact.summary
        else:
            report.summary = risk_answer
        if report.degradation:
            report.summary += " Partial analysis: " + ", ".join(report.degradation) + "."
