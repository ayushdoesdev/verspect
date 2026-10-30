"""Shared helpers for upgrade simulation — AST is the source of truth for usage."""

from __future__ import annotations

from typing import Any, Optional


def build_ast_affected_files(
    usages: list[dict[str, Any]],
    *,
    rule_annotations: Optional[dict[str, list[dict[str, Any]]]] = None,
) -> list[dict[str, Any]]:
    """
    Build affected-file list from AST LibraryUsage records.

    Always returns every file that imports or uses the dependency.
    Migration rules are optional annotations merged by file_path when present.
    """
    files: dict[str, dict[str, Any]] = {}
    annotations = rule_annotations or {}

    for u in usages:
        path = u.get("file_path") or "unknown"
        item = files.get(path)
        if item is None:
            item = {
                "file_path": path,
                "affected_apis": [],
                "usage_sites": [],
                "enclosing_functions": [],
                "enclosing_classes": [],
                "rules": [],
                "reason": "AST usage of this dependency in the repository.",
                "confidence": 0.95,
                "suggested_changes": [],
            }
            files[path] = item

        fqn = u.get("fully_qualified_name") or u.get("symbol")
        if fqn and fqn not in item["affected_apis"]:
            item["affected_apis"].append(fqn)

        site = {
            "symbol": u.get("symbol"),
            "fully_qualified_name": fqn,
            "usage_kind": u.get("usage_kind"),
            "line": u.get("line"),
            "column": u.get("column"),
            "enclosing_function": u.get("enclosing_function"),
            "enclosing_class": u.get("enclosing_class"),
            "code_snippet": u.get("code_snippet"),
        }
        item["usage_sites"].append(site)

        fn = u.get("enclosing_function")
        if fn and fn not in item["enclosing_functions"]:
            item["enclosing_functions"].append(fn)
        cls = u.get("enclosing_class")
        if cls and cls not in item["enclosing_classes"]:
            item["enclosing_classes"].append(cls)

    # Merge optional migration-rule annotations
    for path, rules in annotations.items():
        if path not in files:
            # Rule matched a path not in AST — still show if we somehow have it
            files[path] = {
                "file_path": path,
                "affected_apis": [],
                "usage_sites": [],
                "enclosing_functions": [],
                "enclosing_classes": [],
                "rules": rules,
                "reason": "Migration rule matched this file.",
                "confidence": 0.6,
                "suggested_changes": [],
            }
        else:
            existing = {r.get("symbol") for r in files[path]["rules"]}
            for rule in rules:
                if rule.get("symbol") not in existing:
                    files[path]["rules"].append(rule)
            if rules:
                files[path]["reason"] = (
                    f"AST usage with {len(files[path]['rules'])} migration-rule annotation(s)."
                )
                files[path]["confidence"] = max(
                    float(files[path]["confidence"]),
                    max((float(r.get("confidence") or 0.5) for r in rules), default=0.5),
                )

    # Stable sort by path
    return sorted(files.values(), key=lambda x: x["file_path"])


def rule_annotations_by_file(matched_usages: list[Any]) -> dict[str, list[dict[str, Any]]]:
    """Group engine MatchedUsage / dict matches into per-file rule annotations."""
    out: dict[str, list[dict[str, Any]]] = {}
    for m in matched_usages:
        if hasattr(m, "file_path"):
            path = m.file_path
            rule = m.rule
            entry = {
                "symbol": getattr(rule, "symbol", None),
                "kind": getattr(rule, "kind", None),
                "severity": getattr(rule, "severity", None),
                "description": getattr(rule, "description", None),
                "official_reference": getattr(rule, "official_reference", None),
                "confidence": getattr(m, "match_confidence", None),
            }
        elif isinstance(m, dict):
            path = m.get("file_path") or "unknown"
            entry = m.get("rule") or {
                "symbol": m.get("symbol"),
                "kind": m.get("kind"),
                "severity": m.get("severity"),
                "description": m.get("description") or m.get("reason"),
                "official_reference": m.get("official_reference"),
                "confidence": m.get("confidence"),
            }
        else:
            continue
        out.setdefault(path, []).append(entry)
    return out


def collect_official_references(
    *,
    package_name: str,
    pypi_url: Optional[str] = None,
    github_url: Optional[str] = None,
    home_page: Optional[str] = None,
    documentation_urls: Optional[list[str]] = None,
    engine_refs: Optional[list[str]] = None,
    sources: Optional[dict[str, Any]] = None,
) -> list[str]:
    """Migration docs links only — never security advisories / CVE pages."""
    from app.migration_engine.documentation_fetcher import is_security_url

    refs: list[str] = []
    seen: set[str] = set()

    def add(url: Optional[str], title: str = "") -> None:
        if not url or not isinstance(url, str):
            return
        u = url.strip()
        if not u or u in seen or is_security_url(u, title):
            return
        # Skip bare GitHub security paths even if title empty
        if "/security" in u.lower() and "github.com" in u.lower():
            return
        seen.add(u)
        refs.append(u)

    for r in engine_refs or []:
        if isinstance(r, dict):
            add(r.get("url"), r.get("title") or "")
        else:
            add(r)
    add(pypi_url or f"https://pypi.org/project/{package_name}/")
    # Prefer repo root / docs — not security tab
    if github_url and "/security" not in github_url.lower():
        add(github_url)
    add(home_page)
    for u in documentation_urls or []:
        add(u)

    src = sources or {}
    for u in src.get("documentation_urls") or []:
        add(u)
    pypi = src.get("pypi") or {}
    add(pypi.get("package_url") or pypi.get("pypi_url"))
    for rel in src.get("github_releases") or []:
        add(rel.get("html_url") or rel.get("url"), rel.get("title") or "")
    for note in src.get("release_notes") or []:
        add(note.get("url"), note.get("title") or "")

    return refs


def confidence_label(value: Optional[float]) -> str:
    if value is None:
        return "Low"
    if value >= 0.75:
        return "High"
    if value >= 0.45:
        return "Medium"
    return "Low"


def build_upgrade_advisor(
    *,
    package_name: str,
    current_version: Optional[str],
    latest_version: Optional[str],
    is_outdated: bool,
    has_vulnerabilities: bool,
    vulnerability_count: int,
    critical_vuln_count: int,
    major_behind: int,
    health_score: Optional[float],
    risk_score: Optional[float],
    ai_should_update: Optional[str],
    usage_count: int,
) -> dict[str, Any]:
    """Deterministic upgrade advisor with confidence — never empty."""
    recommended = latest_version or current_version
    benefits: list[str] = []
    risks: list[str] = []
    reasons: list[str] = []

    if has_vulnerabilities:
        benefits.append(
            f"Addresses {vulnerability_count} known vulnerabilit"
            f"{'ies' if vulnerability_count != 1 else 'y'}"
            + (f" including {critical_vuln_count} critical" if critical_vuln_count else "")
        )
        reasons.append("Security advisories exist for the installed version")
    if is_outdated and latest_version:
        benefits.append(f"Catch up to latest release {latest_version}")
        reasons.append(f"Package is behind ({current_version or 'unpinned'} → {latest_version})")
    if health_score is not None and health_score >= 70:
        benefits.append("Target package health looks acceptable")
    if risk_score is not None and risk_score >= 60:
        risks.append(f"Elevated risk score ({risk_score:.0f}/100)")
    if major_behind >= 1:
        risks.append(f"Major version jump ({major_behind} major behind) — expect migration work")
        reasons.append("Major version gap increases migration difficulty")
    if usage_count > 50:
        risks.append(f"High usage footprint ({usage_count} call sites)")
    if not benefits:
        benefits.append("Stay current with upstream maintenance and bug fixes")
    if not risks:
        risks.append("Standard upgrade risk — run tests after bumping the pin")

    # Action
    if critical_vuln_count > 0 or (has_vulnerabilities and major_behind == 0):
        action = "Upgrade now"
        should = "Yes — prioritize this upgrade"
        effort = "low" if major_behind == 0 else "medium"
    elif has_vulnerabilities and major_behind >= 1:
        action = "Security only"
        should = "Upgrade for security; consider an intermediate safe version first"
        effort = "medium"
        recommended = latest_version
    elif major_behind >= 1:
        action = "Major later"
        should = "Plan a major-version migration; patch/minor first if available"
        effort = "high"
    elif is_outdated:
        action = "Upgrade now"
        should = "Yes — routine outdated bump"
        effort = "low"
    else:
        action = "Wait"
        should = "No urgent upgrade — already on latest known version"
        effort = "trivial"
        recommended = current_version

    if ai_should_update:
        reasons.append(f"Prior AI note: {ai_should_update[:240]}")

    conf = 0.55
    if has_vulnerabilities:
        conf += 0.2
    if major_behind >= 1:
        conf -= 0.1
    if current_version and latest_version:
        conf += 0.1
    conf = max(0.3, min(0.95, conf))

    return {
        "should_i_upgrade": should,
        "why": reasons or ["Based on version, vulnerability, and usage signals."],
        "benefits": benefits,
        "risks": risks,
        "estimated_effort": effort,
        "recommended_version": recommended,
        "immediate_action": action,
        "confidence": round(conf, 2),
        "confidence_label": confidence_label(conf),
        "confidence_reason": (
            "Derived from vulnerability status, version gap, health/risk scores, and usage footprint."
        ),
        "package_name": package_name,
        "from_version": current_version,
        "to_version": latest_version,
    }


# ---------------------------------------------------------------------------
# Migration finding classification (Suggested Patches)
# ---------------------------------------------------------------------------

# Deterministic Upgrade Simulator verdicts (AI must never invent/override these).
MIGRATION_STATUS_NO_CHANGE = "no_migration_required"  # positively verified: no changes required
MIGRATION_STATUS_AUTOMATIC = "automatic_migration"  # automatic migration available
MIGRATION_STATUS_MANUAL = "manual_review_required"  # manual review required
MIGRATION_STATUS_UNKNOWN = "unknown"  # insufficient deterministic knowledge
MIGRATION_STATUS_UNRESOLVED = "unresolved"  # insufficient evidence after analysis (incl. AI)

STATUS_TITLE = {
    MIGRATION_STATUS_AUTOMATIC: "Automatic migration available",
    MIGRATION_STATUS_MANUAL: "Manual review required",
    MIGRATION_STATUS_UNKNOWN: "Unknown",
    MIGRATION_STATUS_UNRESOLVED: "Unresolved",
    MIGRATION_STATUS_NO_CHANGE: "No changes required",
}


def normalize_code_snippet(code: Optional[str]) -> str:
    """Normalize for equality checks — ignore review/migrate comment wrappers."""
    if not code:
        return ""
    skip_prefixes = (
        "# Manual review required",
        "# Migrate ",
        "# Review ",
        "# Suggested:",
        "# Upgrade ",
    )
    lines: list[str] = []
    for line in code.splitlines():
        stripped = line.rstrip()
        left = stripped.lstrip()
        if any(left.startswith(p) for p in skip_prefixes):
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def code_differs(current: Optional[str], suggested: Optional[str]) -> bool:
    return normalize_code_snippet(current) != normalize_code_snippet(suggested)


def classify_migration_finding(
    *,
    current_code: Optional[str],
    suggested_code: Optional[str],
    automatic: bool,
    confidence: float,
    validation_status: Optional[str] = None,
    risk_flagged: bool = False,
    unknown: bool = False,
) -> str:
    """
    Exactly one deterministic verdict:
    - automatic_migration
    - manual_review_required
    - unknown
    - no_migration_required
    """
    if unknown:
        return MIGRATION_STATUS_UNKNOWN
    differs = code_differs(current_code, suggested_code)
    if (
        automatic
        and differs
        and confidence >= 0.75
        and validation_status == "validated"
    ):
        return MIGRATION_STATUS_AUTOMATIC
    if risk_flagged or differs:
        return MIGRATION_STATUS_MANUAL
    return MIGRATION_STATUS_NO_CHANGE


def build_migration_finding(
    *,
    file_path: str,
    line: Optional[int],
    symbol: Optional[str],
    current_code: Optional[str],
    suggested_code: Optional[str],
    explanation: str,
    confidence: float,
    automatic: bool,
    official_reference: Optional[str] = None,
    validation_status: Optional[str] = None,
    unified_diff: Optional[str] = None,
    risk_flagged: bool = False,
    unknown: bool = False,
) -> dict[str, Any]:
    """
    Build a finding with migration_status.

    Never emit identical current/suggested code as a patch.
    Manual/unknown findings omit suggested_code and point to docs instead.
    """
    status = classify_migration_finding(
        current_code=current_code,
        suggested_code=suggested_code,
        automatic=automatic,
        confidence=confidence,
        validation_status=validation_status,
        risk_flagged=risk_flagged,
        unknown=unknown,
    )
    differs = code_differs(current_code, suggested_code)
    base = {
        "file_path": file_path,
        "line": line,
        "symbol": symbol,
        "current_code": current_code or "",
        "confidence": confidence,
        "official_reference": official_reference,
        "validation_status": validation_status,
        "migration_status": status,
    }

    if status == MIGRATION_STATUS_AUTOMATIC and differs:
        return {
            **base,
            "suggested_code": suggested_code or "",
            "explanation": explanation,
            "automatic": True,
            "unified_diff": unified_diff,
            "status_title": STATUS_TITLE[MIGRATION_STATUS_AUTOMATIC],
            "status_detail": explanation,
        }

    if status == MIGRATION_STATUS_MANUAL:
        return {
            **base,
            "suggested_code": None,
            "explanation": explanation,
            "automatic": False,
            "unified_diff": None,
            "validation_status": validation_status or "needs_review",
            "status_title": STATUS_TITLE[MIGRATION_STATUS_MANUAL],
            "status_detail": explanation
            or (
                "This usage may be affected by the upgrade. Review official documentation — "
                "no high-confidence automatic replacement is available."
            ),
        }

    if status == MIGRATION_STATUS_UNKNOWN:
        return {
            **base,
            "suggested_code": None,
            "explanation": explanation,
            "automatic": False,
            "unified_diff": None,
            "validation_status": validation_status or "needs_review",
            "status_title": STATUS_TITLE[MIGRATION_STATUS_UNKNOWN],
            "status_detail": explanation
            or (
                "Insufficient deterministic migration knowledge for this library/version range. "
                "Do not treat this as a clean upgrade."
            ),
        }

    return {
        **base,
        "suggested_code": None,
        "explanation": explanation
        or "No code change is required for this usage — positively verified against migration rules.",
        "automatic": False,
        "unified_diff": None,
        "migration_status": MIGRATION_STATUS_NO_CHANGE,
        "status_title": STATUS_TITLE[MIGRATION_STATUS_NO_CHANGE],
        "status_detail": explanation
        or "This call site does not match a breaking or deprecated API for this upgrade range.",
    }


def findings_to_suggested_changes(findings: list[Any]) -> list[dict[str, Any]]:
    """Convert engine MigrationFinding objects/dicts into UI suggested_changes rows."""
    out: list[dict[str, Any]] = []
    for f in findings:
        if hasattr(f, "model_dump"):
            data = f.model_dump()
        elif isinstance(f, dict):
            data = f
        else:
            continue
        status = data.get("status") or MIGRATION_STATUS_MANUAL
        conf = float(data.get("confidence") or 0.0)
        current = data.get("current_code")
        suggested = data.get("suggested_code")
        automatic = status == MIGRATION_STATUS_AUTOMATIC
        finding = build_migration_finding(
            file_path=data.get("file_path") or "",
            line=data.get("line"),
            symbol=data.get("symbol"),
            current_code=current,
            suggested_code=suggested if automatic else None,
            explanation=data.get("reason") or "",
            confidence=conf,
            automatic=automatic,
            official_reference=data.get("official_reference"),
            validation_status="validated" if automatic else "needs_review",
            unified_diff=data.get("unified_diff") if automatic else None,
            risk_flagged=status == MIGRATION_STATUS_MANUAL,
            unknown=status == MIGRATION_STATUS_UNKNOWN,
        )
        # Honor engine status even when build_migration_finding reclassifies
        finding["migration_status"] = status
        finding["status_title"] = STATUS_TITLE.get(status, STATUS_TITLE[MIGRATION_STATUS_MANUAL])
        if status == MIGRATION_STATUS_AUTOMATIC:
            finding["replacement"] = data.get("replacement")
            finding["suggested_code"] = suggested
            finding["unified_diff"] = data.get("unified_diff")
            finding["automatic"] = True
        else:
            finding["suggested_code"] = None
            finding["unified_diff"] = None
            finding["automatic"] = False
        if data.get("reference_title"):
            finding["reference_title"] = data["reference_title"]
        if data.get("replacement") and status == MIGRATION_STATUS_AUTOMATIC:
            finding["replacement"] = data["replacement"]
        out.append(finding)
    return out


def sanitize_engine_error(exc: BaseException) -> str:
    """Map internal persistence failures to user-safe simulation messages."""
    name = type(exc).__name__.lower()
    raw = str(exc)
    lowered = raw.lower()
    if (
        "uniqueviolation" in name
        or "integrityerror" in name
        or "unique constraint" in lowered
        or "duplicate key" in lowered
        or "uq_kb_normalized_eco" in lowered
    ):
        return (
            "Shared migration knowledge was updated concurrently. "
            "Deterministic analysis continued where possible."
        )
    if any(
        token in lowered
        for token in ("psycopg", "sqlalchemy", "violates", "postgresql", "asyncpg")
    ):
        return (
            "Migration knowledge update failed unexpectedly. "
            "Deterministic analysis continued where possible."
        )
    return raw[:500]
