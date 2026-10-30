"""Ecosystem-agnostic upgrade evidence collection.

Collects registry metadata, releases, changelogs, and docs for ANY supported
ecosystem. Does not encode per-package upgrade rules.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from app.core.logging import get_logger
from app.migration_engine.cache import MigrationCache
from app.scanners.pypi import compare_versions
from app.services.upgrade_intelligence.changelog import extract_documented_changes
from app.services.upgrade_intelligence.models import EvidenceBundle, EvidenceItem
from app.services.upgrade_sources import UpgradeSourceCollector
from packaging.version import InvalidVersion, Version

logger = get_logger(__name__)

_ECOSYSTEM_ALIASES = {
    "pypi": "pypi",
    "python": "pypi",
    "npm": "npm",
    "javascript": "npm",
    "typescript": "npm",
    "node": "npm",
    "nodejs": "npm",
    "go": "go",
    "golang": "go",
    "maven": "maven",
    "java": "maven",
    "crates.io": "crates.io",
    "crates": "crates.io",
    "rust": "crates.io",
    "packagist": "packagist",
    "php": "packagist",
    "composer": "packagist",
    "rubygems": "rubygems",
    "ruby": "rubygems",
    "gem": "rubygems",
}

SUPPORTED_EVIDENCE_ECOSYSTEMS = frozenset(_ECOSYSTEM_ALIASES.values())

_HEADERS = {"User-Agent": "Verspect-DependencyIntelligence/1.0"}
_CACHE_TTL = 60 * 60 * 12


def normalize_ecosystem(value: str | None) -> str:
    raw = (value or "pypi").strip().lower()
    return _ECOSYSTEM_ALIASES.get(raw, raw)


class GeneralizedEvidenceCollector:
    """Collect whatever reliable public metadata exists for current → target."""

    def __init__(self, timeout: float = 20.0, cache: Optional[MigrationCache] = None) -> None:
        self.timeout = timeout
        self.cache = cache if cache is not None else MigrationCache()
        self._legacy = UpgradeSourceCollector(timeout=timeout)

    def collect(
        self,
        *,
        package_name: str,
        from_version: str,
        to_version: str,
        ecosystem: str = "PyPI",
        github_repo_url: Optional[str] = None,
        existing_releases: Optional[list[dict[str, Any]]] = None,
        cve_summaries: Optional[list[str]] = None,
        skip_network: bool = False,
        force_refresh: bool = False,
    ) -> EvidenceBundle:
        eco = normalize_ecosystem(ecosystem)
        cache_key = f"upg-ev:{eco}:{package_name}:{from_version}:{to_version}"
        if not force_refresh and not skip_network:
            cached = self.cache.get_json(cache_key)
            if isinstance(cached, dict) and cached.get("package_name"):
                try:
                    return EvidenceBundle.model_validate(cached)
                except Exception:  # noqa: BLE001
                    pass

        bundle = EvidenceBundle(
            package_name=package_name,
            ecosystem=eco,
            from_version=from_version,
            to_version=to_version,
            github_repo_url=github_repo_url,
        )
        if skip_network:
            return bundle

        registry, degradation = self._fetch_registry(eco, package_name, from_version, to_version)
        bundle.registry = registry
        bundle.degradation.extend(degradation)
        bundle.latest_version = registry.get("latest_version")
        if not bundle.github_repo_url:
            bundle.github_repo_url = registry.get("github_repo_url") or registry.get("repository")

        # GitHub releases + changelog URLs — reuse existing collector (not PyPI-only for GH).
        try:
            sources = self._legacy.collect(
                package_name=package_name,
                from_version=from_version,
                to_version=to_version,
                github_repo_url=bundle.github_repo_url,
                existing_releases=existing_releases,
                cve_summaries=cve_summaries,
                ecosystem=eco,
                skip_pypi=True,
            )
            bundle.raw_sources = sources
            bundle.github_releases = list(sources.get("github_releases") or [])
            bundle.release_notes = list(sources.get("release_notes") or [])
            bundle.documentation_urls = list(sources.get("documentation_urls") or [])
            bundle.breaking_change_hints = [str(x) for x in (sources.get("breaking_change_hints") or [])]
            bundle.deprecated_hints = [str(x) for x in (sources.get("deprecated_hints") or [])]
            bundle.security_hints = [str(x) for x in (sources.get("security_fixes") or [])]
        except Exception as exc:  # noqa: BLE001
            logger.warning("upgrade_evidence_github_failed", package=package_name, error=str(exc)[:300])
            bundle.degradation.append("release_notes_unavailable")

        # Registry-provided changelog / homepage extras.
        self._ingest_registry_docs(bundle, registry)

        notes_for_extract = list(bundle.release_notes) + list(bundle.changelog_excerpts) + list(
            bundle.migration_guide_excerpts
        )
        bundle.extracted_changes = extract_documented_changes(notes_for_extract)

        bundle.items = self._normalize_items(bundle)
        # Do not cache a github-backed collect that produced no notes — retry next time.
        skip_cache = bool(
            bundle.github_repo_url and not bundle.release_notes and not bundle.github_releases
        )
        if not skip_cache:
            try:
                self.cache.set_json(cache_key, bundle.model_dump(), ttl=_CACHE_TTL)
            except Exception:  # noqa: BLE001
                pass
        return bundle

    def _fetch_registry(
        self,
        ecosystem: str,
        package_name: str,
        from_version: str,
        to_version: str,
    ) -> tuple[dict[str, Any], list[str]]:
        degradation: list[str] = []
        try:
            data = self._registry_payload(ecosystem, package_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "upgrade_registry_unavailable",
                ecosystem=ecosystem,
                package=package_name,
                error=str(exc)[:300],
            )
            return {}, ["package_registry_unavailable"]
        if not data:
            return {}, ["unsupported_package"] if ecosystem not in SUPPORTED_EVIDENCE_ECOSYSTEMS else [
                "unknown_package"
            ]

        latest = data.get("latest_version") or data.get("version")
        comparison: dict[str, Any] = {}
        try:
            if from_version and to_version:
                comparison = compare_versions(from_version, to_version)
                comparison["target_is_newer"] = bool(comparison.get("is_outdated"))
        except Exception:  # noqa: BLE001
            comparison = {"is_outdated": from_version != to_version}
        if not from_version or not to_version:
            degradation.append("unknown_version")
        data = {**data, **comparison, "latest_version": latest}
        versions = data.get("releases") or data.get("versions") or []
        if isinstance(versions, dict):
            versions = [{"version": k} for k in list(versions.keys())[:40]]
        data["releases"] = versions[:40] if isinstance(versions, list) else []
        return data, degradation

    def _registry_payload(self, ecosystem: str, package_name: str) -> dict[str, Any]:
        if ecosystem == "pypi":
            from app.scanners.pypi import PyPIClient

            info = PyPIClient(timeout=self.timeout).get_package_info(package_name) or {}
            meta = info.get("info") or {}
            urls = meta.get("project_urls") or {}
            github = None
            for url in list(urls.values()) + [meta.get("home_page"), meta.get("project_url")]:
                if url and "github.com" in str(url).lower():
                    github = str(url)
                    break
            return {
                "latest_version": meta.get("version"),
                "summary": meta.get("summary"),
                "home_page": meta.get("home_page"),
                "project_urls": urls,
                "description_excerpt": (meta.get("description") or "")[:4000],
                "github_repo_url": github,
                "license_raw": meta.get("license"),
            }
        if ecosystem == "npm":
            from app.scanners.npm import NpmClient

            info = NpmClient(timeout=self.timeout).get_package_info(package_name) or {}
            latest = (info.get("dist-tags") or {}).get("latest")
            versions = info.get("versions") or {}
            latest_info = versions.get(latest, {}) if latest else {}
            repo = latest_info.get("repository") or info.get("repository") or {}
            repo_url = repo.get("url") if isinstance(repo, dict) else repo
            homepage = latest_info.get("homepage") or info.get("homepage")
            return {
                "latest_version": latest,
                "summary": latest_info.get("description") or info.get("description"),
                "home_page": homepage,
                "github_repo_url": repo_url,
                "license_raw": latest_info.get("license"),
                "project_urls": {"homepage": homepage, "repository": repo_url},
                "description_excerpt": (info.get("readme") or "")[:4000],
                "releases": [{"version": v} for v in list(versions.keys())[-40:]],
            }
        if ecosystem == "crates.io":
            from app.scanners.registries import CratesIoClient

            return CratesIoClient(timeout=self.timeout).extract_version_info(package_name) or {}
        if ecosystem == "packagist":
            from app.scanners.registries import PackagistClient

            return PackagistClient(timeout=self.timeout).extract_version_info(package_name) or {}
        if ecosystem == "rubygems":
            from app.scanners.registries import RubyGemsClient

            return RubyGemsClient(timeout=self.timeout).extract_version_info(package_name) or {}
        if ecosystem == "maven":
            from app.scanners.registries import MavenCentralClient

            return MavenCentralClient(timeout=self.timeout).extract_version_info(package_name) or {}
        if ecosystem == "go":
            return self._fetch_go_module(package_name)
        return {}

    def _fetch_go_module(self, module_path: str) -> dict[str, Any]:
        from app.scanners.go_modules import GoModulesClient, _escape_module_path

        github = None
        if module_path.startswith("github.com/"):
            parts = module_path.split("/")
            if len(parts) >= 3:
                github = f"https://github.com/{parts[1]}/{parts[2]}"

        versions: list[str] = []
        try:
            url = f"https://proxy.golang.org/{_escape_module_path(module_path)}/@v/list"
            with httpx.Client(timeout=self.timeout, headers=_HEADERS, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code != 404:
                    resp.raise_for_status()
                    versions = [v.strip() for v in resp.text.splitlines() if v.strip()]
        except Exception as exc:  # noqa: BLE001
            logger.warning("upgrade_go_list_failed", module=module_path, error=str(exc)[:300])

        latest = self._highest_go_version(versions)
        if not latest:
            info = GoModulesClient(timeout=self.timeout).get_latest(module_path) or {}
            tag = info.get("Version")
            if tag:
                latest = str(tag).lstrip("v")
                if str(tag) not in versions:
                    versions.append(str(tag))

        return {
            "latest_version": latest,
            "github_repo_url": github,
            "home_page": f"https://pkg.go.dev/{module_path}",
            "releases": [{"version": v} for v in versions[-40:]],
            "summary": None,
        }

    @staticmethod
    def _highest_go_version(versions: list[str]) -> Optional[str]:
        best: Optional[tuple[Version, str]] = None
        for raw in versions:
            token = raw.strip()
            if not token:
                continue
            try:
                parsed = Version(token[1:] if token[:1] in {"v", "V"} and token[1:2].isdigit() else token)
            except InvalidVersion:
                continue
            if best is None or parsed > best[0]:
                best = (parsed, token.lstrip("vV") if token[:1] in {"v", "V"} and token[1:2].isdigit() else token)
        return best[1] if best else None

    def _ingest_registry_docs(self, bundle: EvidenceBundle, registry: dict[str, Any]) -> None:
        excerpt = registry.get("description_excerpt")
        if excerpt and not bundle.release_notes:
            bundle.release_notes.append(
                {
                    "version": f"{bundle.from_version}..{bundle.to_version}",
                    "source": "registry_description",
                    "text": excerpt,
                }
            )
        urls = registry.get("project_urls") or {}
        if isinstance(urls, dict):
            for label, url in urls.items():
                if not url:
                    continue
                lower = f"{label} {url}".lower()
                kind = "docs"
                if any(x in lower for x in ("changelog", "history", "news", "release")):
                    kind = "changelog"
                elif any(x in lower for x in ("migrat", "upgrade", "breaking")):
                    kind = "migration_guide"
                bundle.documentation_urls.append({"type": kind, "url": str(url), "label": str(label)})

    def _normalize_items(self, bundle: EvidenceBundle) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        if bundle.registry:
            items.append(
                EvidenceItem(
                    kind="registry_metadata",
                    text=(bundle.registry.get("summary") or f"{bundle.package_name} registry metadata")[:500],
                    source=bundle.registry.get("home_page"),
                    reliability="high",
                    untrusted=True,
                )
            )
        for note in bundle.release_notes[:12]:
            items.append(
                EvidenceItem(
                    kind="release_notes",
                    text=(note.get("text") or "")[:800],
                    source=str(note.get("url") or note.get("source") or ""),
                    reliability="medium",
                    untrusted=True,
                )
            )
        for rel in bundle.github_releases[:8]:
            items.append(
                EvidenceItem(
                    kind="github_release",
                    text=((rel.get("name") or "") + "\n" + (rel.get("body") or ""))[:800],
                    source=rel.get("url"),
                    reliability="medium",
                    untrusted=True,
                )
            )
        for change in bundle.extracted_changes[:40]:
            items.append(
                EvidenceItem(
                    kind=f"extracted_{change.get('kind')}",
                    text=f"{change.get('identifier')}: {change.get('line')}",
                    source=str(change.get("source") or ""),
                    reliability="medium",
                    untrusted=True,
                )
            )
        return items
