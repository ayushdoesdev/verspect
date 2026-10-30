"""OSV vulnerability checker.

Package names are mapped per ecosystem. PEP 503 hyphenation is PyPI-only —
Maven coordinates (`group:artifact`) must be sent unchanged.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.enums import AlertSeverity
from app.core.logging import get_logger
from app.scanners.normalize import normalize_package_name

logger = get_logger(__name__)


class OSVUnavailableError(Exception):
    """OSV could not be queried. Callers must not treat this as zero vulnerabilities."""

OSV_QUERY_URL = "https://api.osv.dev/v1/query"
OSV_QUERYBATCH_URL = "https://api.osv.dev/v1/querybatch"
OSV_VULN_URL = "https://api.osv.dev/v1/vulns/{vuln_id}"

# Internal analyzer ecosystem strings → OSV ecosystem identifiers.
_OSV_ECOSYSTEMS: dict[str, str] = {
    "pypi": "PyPI",
    "npm": "npm",
    "go": "Go",
    "maven": "Maven",
    "packagist": "Packagist",
    "rubygems": "RubyGems",
    "crates.io": "crates.io",
    "crates": "crates.io",
    "cargo": "crates.io",
}


def osv_ecosystem_name(ecosystem: str) -> str:
    """Return the OSV ecosystem identifier for an internal ecosystem string."""
    key = (ecosystem or "PyPI").strip()
    return _OSV_ECOSYSTEMS.get(key.lower(), key)


def package_name_for_osv(package_name: str, ecosystem: str) -> str:
    """Normalize a package name only when the ecosystem requires it."""
    name = (package_name or "").strip()
    eco = osv_ecosystem_name(ecosystem)
    if eco == "PyPI":
        return normalize_package_name(name)
    if eco == "npm":
        return name.lower()
    return name


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def severity_from_osv(vuln: dict[str, Any]) -> tuple[str, Optional[float], Optional[str]]:
    """Map OSV severity / database_specific to our AlertSeverity + CVSS."""
    cvss_score = None
    cvss_vector = None

    for sev in vuln.get("severity") or []:
        if sev.get("type") == "CVSS_V3":
            score = sev.get("score")
            if isinstance(score, (int, float)):
                cvss_score = float(score)
            elif isinstance(score, str) and score.startswith("CVSS:"):
                cvss_vector = score

    db_specific = vuln.get("database_specific") or {}
    if cvss_score is None and "cvss" in db_specific:
        try:
            cvss_score = float(db_specific["cvss"].get("score") or db_specific["cvss"])
        except (TypeError, ValueError, AttributeError):
            pass

    severity_label = (db_specific.get("severity") or "").upper()
    if severity_label in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
        mapped = severity_label.lower()
    elif cvss_score is not None:
        if cvss_score >= 9.0:
            mapped = AlertSeverity.CRITICAL.value
        elif cvss_score >= 7.0:
            mapped = AlertSeverity.HIGH.value
        elif cvss_score >= 4.0:
            mapped = AlertSeverity.MEDIUM.value
        else:
            mapped = AlertSeverity.LOW.value
    else:
        mapped = AlertSeverity.MEDIUM.value

    return mapped, cvss_score, cvss_vector


def extract_fixed_version(
    vuln: dict[str, Any],
    package_name: str,
    ecosystem: str = "PyPI",
) -> tuple[Optional[str], Optional[str], list]:
    """Return (fixed_version, introduced_version, affected_ranges)."""
    fixed = None
    introduced = None
    affected_versions: list = []
    normalized = package_name_for_osv(package_name, ecosystem)
    osv_eco = osv_ecosystem_name(ecosystem)

    for affected in vuln.get("affected") or []:
        pkg = affected.get("package") or {}
        if package_name_for_osv(pkg.get("name") or "", ecosystem) != normalized:
            continue
        affected_ecosystem = (pkg.get("ecosystem") or "").lower()
        if affected_ecosystem not in {osv_eco.lower(), ""}:
            continue
        for ver in affected.get("versions") or []:
            affected_versions.append(ver)
        for r in affected.get("ranges") or []:
            for event in r.get("events") or []:
                if "introduced" in event and event["introduced"] != "0":
                    introduced = event["introduced"]
                if "fixed" in event:
                    fixed = event["fixed"]
    return fixed, introduced, affected_versions


class OSVClient:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self._query_cache: dict[tuple[str, str, str], list[dict[str, Any]]] = {}

    def _query_payload(
        self,
        package_name: str,
        version: Optional[str],
        ecosystem: str,
    ) -> dict[str, Any]:
        osv_eco = osv_ecosystem_name(ecosystem)
        payload: dict[str, Any] = {
            "package": {
                "name": package_name_for_osv(package_name, osv_eco),
                "ecosystem": osv_eco,
            }
        }
        if version:
            payload["version"] = version
        return payload

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def query_package(
        self,
        package_name: str,
        version: Optional[str] = None,
        ecosystem: str = "PyPI",
    ) -> list[dict[str, Any]]:
        osv_eco = osv_ecosystem_name(ecosystem)
        name = package_name_for_osv(package_name, osv_eco)
        cache_key = (osv_eco, name, version or "")
        cached = self._query_cache.get(cache_key)
        if cached is not None:
            return cached

        payload = self._query_payload(package_name, version, ecosystem)
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(OSV_QUERY_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            vulns = data.get("vulns") or []
        self._query_cache[cache_key] = vulns
        return vulns

    def query_packages_batch(
        self,
        items: list[tuple[str, Optional[str], str]],
    ) -> list[list[dict[str, Any]]]:
        """Query many packages via /v1/querybatch, then hydrate vuln documents.

        Returns a list aligned with `items`. Failures for a single package yield [].
        """
        if not items:
            return []
        queries = [self._query_payload(name, version, eco) for name, version, eco in items]
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(OSV_QUERYBATCH_URL, json={"queries": queries})
                response.raise_for_status()
                results = (response.json() or {}).get("results") or []
        except Exception as exc:
            logger.error("osv_querybatch_failed", error=str(exc), count=len(items))
            return [self.query_package(n, v, e) for n, v, e in items]

        vuln_ids: list[str] = []
        per_item_ids: list[list[str]] = []
        for row in results:
            ids = [v.get("id") for v in (row.get("vulns") or []) if v.get("id")]
            per_item_ids.append(ids)
            vuln_ids.extend(ids)

        by_id: dict[str, dict[str, Any]] = {}
        for vuln_id in dict.fromkeys(vuln_ids):
            doc = self._fetch_vuln(vuln_id)
            if doc:
                by_id[vuln_id] = doc

        out: list[list[dict[str, Any]]] = []
        for ids in per_item_ids:
            out.append([by_id[i] for i in ids if i in by_id])
        while len(out) < len(items):
            out.append([])
        return out[: len(items)]

    def _fetch_vuln(self, vuln_id: str) -> Optional[dict[str, Any]]:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(OSV_VULN_URL.format(vuln_id=vuln_id))
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            logger.warning("osv_vuln_fetch_failed", osv_id=vuln_id, error=str(exc))
            return None

    def normalize_vuln(
        self,
        vuln: dict[str, Any],
        package_name: str,
        ecosystem: str = "PyPI",
    ) -> dict[str, Any]:
        severity, cvss_score, cvss_vector = severity_from_osv(vuln)
        fixed, introduced, affected_versions = extract_fixed_version(
            vuln, package_name, ecosystem
        )
        aliases = vuln.get("aliases") or []
        cve_id = next((a for a in aliases if a.startswith("CVE-")), None)

        refs = []
        for ref in vuln.get("references") or []:
            refs.append({"type": ref.get("type"), "url": ref.get("url")})

        osv_eco = osv_ecosystem_name(ecosystem)
        return {
            "osv_id": vuln.get("id"),
            "cve_id": cve_id,
            "aliases": aliases,
            "summary": vuln.get("summary") or vuln.get("details", "")[:500] or "No summary",
            "details": vuln.get("details"),
            "severity": severity,
            "cvss_score": cvss_score,
            "cvss_vector": cvss_vector,
            "affected_versions": affected_versions,
            "fixed_version": fixed,
            "introduced_version": introduced,
            "is_fixable": fixed is not None,
            "published_at": _parse_dt(vuln.get("published")),
            "modified_at": _parse_dt(vuln.get("modified")),
            "references": refs,
            "raw_osv": vuln,
            "package_name": package_name,
            "ecosystem": osv_eco,
        }

    def check_dependency(
        self,
        package_name: str,
        version: Optional[str] = None,
        ecosystem: str = "PyPI",
    ) -> list[dict[str, Any]]:
        try:
            vulns = self.query_package(package_name, version, ecosystem)
        except Exception as exc:
            logger.error("osv_query_failed", package=package_name, error=str(exc))
            raise OSVUnavailableError(str(exc)) from exc
        return [self.normalize_vuln(v, package_name, ecosystem) for v in vulns]
