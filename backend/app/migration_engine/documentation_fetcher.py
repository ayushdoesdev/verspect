"""Generic documentation / changelog / migration-guide fetcher for any package.

Pipeline B only — never treats security advisories as migration docs.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.core.logging import get_logger
from app.migration_engine.cache import MigrationCache, content_hash
from app.scanners.normalize import normalize_package_name

logger = get_logger(__name__)

# Pipeline A sources — never used for migration analysis
_SECURITY_URL_MARKERS = (
    "/security",
    "/advisories",
    "security.github.com",
    "github.com/advisories",
    "/security/advisories",
    "nvd.nist.gov",
    "cve.mitre.org",
    "osv.dev",
    "snyk.io/vuln",
    "pypi.org/project/",  # allow pypi itself; see _is_security_url for nuance
)

_SECURITY_LABEL_MARKERS = (
    "security",
    "advisory",
    "advisories",
    "cve",
    "vulnerability",
    "vulnerabilities",
    "osv",
)

_MIGRATION_SOURCE_TYPES = frozenset(
    {
        "migration_guide",
        "upgrade_guide",
        "release_notes",
        "changelog",
        "docs",
        "github_release",
        "pypi",
    }
)


def _strip_html(text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_security_url(url: str, title: str = "") -> bool:
    """True when URL/title belongs to Pipeline A (security intelligence)."""
    blob = f"{title} {url}".lower()
    if any(m in blob for m in _SECURITY_LABEL_MARKERS) and any(
        x in blob
        for x in (
            "/security",
            "advisories",
            "advisory",
            "cve",
            "osv",
            "nvd.nist",
            "vulnerab",
        )
    ):
        return True
    lower = (url or "").lower()
    if "/security/advisories" in lower or "security.github.com" in lower:
        return True
    if "github.com" in lower and "/security" in lower:
        return True
    if any(
        host in lower
        for host in ("nvd.nist.gov", "cve.mitre.org", "osv.dev", "snyk.io/vuln")
    ):
        return True
    return False


def is_migration_source(source_type: str, url: str = "", title: str = "") -> bool:
    if is_security_url(url, title):
        return False
    st = (source_type or "").lower()
    if st in {"security", "advisory", "cve", "osv"}:
        return False
    return st in _MIGRATION_SOURCE_TYPES or st == "github"


class DocumentationFetcher:
    """Fetch official docs, changelogs, and migration guides — library-agnostic."""

    def __init__(self, cache: Optional[MigrationCache] = None, timeout: float = 30.0) -> None:
        self.cache = cache or MigrationCache()
        self.timeout = timeout

    def discover_urls(self, pypi_info: dict[str, Any]) -> list[dict[str, str]]:
        """Extract migration-related URLs from PyPI project metadata (Pipeline B)."""
        found: list[dict[str, str]] = []
        info = pypi_info.get("info") or pypi_info
        urls = info.get("project_urls") or {}
        home = info.get("home_page") or info.get("project_url")
        if home:
            urls = {**{"Homepage": home}, **urls}

        for label, url in urls.items():
            if not url or not isinstance(url, str):
                continue
            if is_security_url(url, label):
                continue
            lower = f"{label} {url}".lower()
            source_type = "docs"
            if any(k in lower for k in ("changelog", "changes", "history", "news")):
                source_type = "changelog"
            elif any(k in lower for k in ("release note", "releases")):
                source_type = "release_notes"
            elif any(k in lower for k in ("migrat", "upgrade", "breaking")):
                source_type = "migration_guide"
            elif "github.com" in lower and "/releases" in lower:
                source_type = "github_release"
            elif "github.com" in lower and "/security" in lower:
                continue
            elif "github.com" in lower:
                source_type = "github"
            elif any(k in lower for k in ("doc", "readthedocs", "documentation")):
                source_type = "docs"
            else:
                continue
            found.append({"source_type": source_type, "url": url.strip(), "title": label})

        # Prefer migration guides / changelogs / release notes first
        priority = {
            "migration_guide": 0,
            "upgrade_guide": 0,
            "changelog": 1,
            "release_notes": 1,
            "github_release": 2,
            "docs": 3,
            "github": 4,
            "pypi": 5,
        }
        found.sort(key=lambda x: priority.get(x["source_type"], 9))

        seen: set[str] = set()
        unique = []
        for item in found:
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            unique.append(item)
        return unique

    def fetch_url(self, url: str, limit: int = 20000) -> dict[str, Any]:
        if is_security_url(url):
            return {
                "url": url,
                "content": None,
                "content_hash": None,
                "http_status": None,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "error": "security_source_excluded_from_migration_pipeline",
            }

        cache_key = self.cache.docs_key(url)
        cached = self.cache.get_json(cache_key)
        if cached:
            return cached

        result: dict[str, Any] = {
            "url": url,
            "content": None,
            "content_hash": None,
            "http_status": None,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "error": None,
        }
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": "DependencyIntelligence/1.0"})
                result["http_status"] = resp.status_code
                if resp.status_code != 200:
                    result["error"] = f"HTTP {resp.status_code}"
                    return result
                text = resp.text
                ctype = (resp.headers.get("content-type") or "").lower()
                if "html" in ctype or text.lstrip().lower().startswith("<!doctype") or "<html" in text[:200].lower():
                    text = _strip_html(text)
                text = text[:limit]
                result["content"] = text
                result["content_hash"] = content_hash(text)
                self.cache.set_json(cache_key, result)
        except Exception as exc:
            logger.warning("documentation_fetch_failed", url=url, error=str(exc))
            result["error"] = str(exc)
        return result

    def fetch_all_discovered(
        self,
        package_name: str,
        pypi_info: dict[str, Any],
        max_sources: int = 6,
    ) -> list[dict[str, Any]]:
        urls = [
            u
            for u in self.discover_urls(pypi_info)
            if is_migration_source(u.get("source_type", ""), u.get("url", ""), u.get("title", ""))
        ][:max_sources]
        results = []
        for item in urls:
            fetched = self.fetch_url(item["url"])
            if fetched.get("error") == "security_source_excluded_from_migration_pipeline":
                continue
            results.append({**item, **fetched, "package_name": package_name})
        return results

    def fetch_pypi_description(self, package_name: str) -> dict[str, Any]:
        name = normalize_package_name(package_name)
        url = f"https://pypi.org/pypi/{name}/json"
        cache_key = f"pypi_meta:{name}"
        cached = self.cache.get_json(cache_key)
        if cached:
            return cached
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code != 200:
                    return {}
                data = resp.json()
                self.cache.set_json(cache_key, data, ttl=60 * 60 * 12)
                return data
        except Exception as exc:
            logger.warning("pypi_meta_fetch_failed", package=name, error=str(exc))
            return {}
