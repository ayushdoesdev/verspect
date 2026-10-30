"""Generic release / changelog fetcher for any PyPI package."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import httpx
from packaging.version import InvalidVersion, Version

from app.core.logging import get_logger
from app.migration_engine.cache import MigrationCache, content_hash
from app.scanners.normalize import normalize_package_name

logger = get_logger(__name__)


def _parse_version(value: str) -> Optional[Version]:
    try:
        return Version(value.lstrip("v"))
    except InvalidVersion:
        return None


def version_in_range(ver: str, from_v: str, to_v: str) -> bool:
    current = _parse_version(ver)
    lo = _parse_version(from_v)
    hi = _parse_version(to_v)
    if not current or not lo or not hi:
        return ver.lstrip("v") in {from_v, to_v, f"v{to_v}", f"v{from_v}"}
    return lo < current <= hi


class ReleaseFetcher:
    """Fetch GitHub releases and PyPI version history — library-agnostic."""

    def __init__(self, cache: Optional[MigrationCache] = None, timeout: float = 30.0) -> None:
        self.cache = cache or MigrationCache()
        self.timeout = timeout

    def parse_github_repo(self, url: Optional[str]) -> Optional[tuple[str, str]]:
        if not url or "github.com" not in url:
            return None
        try:
            parts = url.rstrip("/").split("github.com/")[-1].split("/")
            if len(parts) >= 2:
                return parts[0], parts[1].removesuffix(".git")
        except Exception:
            return None
        return None

    def fetch_github_releases(
        self,
        owner: str,
        repo: str,
        from_version: str,
        to_version: str,
        per_page: int = 40,
    ) -> list[dict[str, Any]]:
        cache_key = f"gh_rel:{owner}/{repo}:{from_version}:{to_version}"
        cached = self.cache.get_json(cache_key)
        if cached is not None:
            return cached

        url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        results: list[dict[str, Any]] = []
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(
                    url,
                    headers={
                        "Accept": "application/vnd.github+json",
                        "User-Agent": "DependencyIntelligence/1.0",
                    },
                    params={"per_page": per_page},
                )
                if resp.status_code != 200:
                    return []
                for rel in resp.json() if isinstance(resp.json(), list) else []:
                    tag = (rel.get("tag_name") or "").lstrip("v")
                    if not tag:
                        continue
                    if not version_in_range(tag, from_version, to_version) and tag != to_version.lstrip("v"):
                        continue
                    body = rel.get("body") or ""
                    results.append(
                        {
                            "version": tag,
                            "title": rel.get("name"),
                            "body": body[:20000],
                            "url": rel.get("html_url"),
                            "published_at": rel.get("published_at"),
                            "source": "github_release",
                            "content_hash": content_hash(body),
                        }
                    )
            self.cache.set_json(cache_key, results)
        except Exception as exc:
            logger.warning("github_releases_failed", repo=f"{owner}/{repo}", error=str(exc))
        return results

    def fetch_pypi_versions(self, package_name: str) -> list[str]:
        name = normalize_package_name(package_name)
        cache_key = f"pypi_versions:{name}"
        cached = self.cache.get_json(cache_key)
        if cached is not None:
            return cached
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(f"https://pypi.org/pypi/{name}/json")
                if resp.status_code != 200:
                    return []
                releases = list((resp.json().get("releases") or {}).keys())

                def sort_key(v: str):
                    try:
                        return Version(v)
                    except InvalidVersion:
                        return Version("0")

                releases.sort(key=sort_key)
                self.cache.set_json(cache_key, releases, ttl=60 * 60 * 6)
                return releases
        except Exception:
            return []

    def collect_for_range(
        self,
        package_name: str,
        from_version: str,
        to_version: str,
        github_url: Optional[str] = None,
        pypi_info: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        github_url = github_url or self._github_from_pypi(pypi_info or {})
        releases: list[dict[str, Any]] = []
        parsed = self.parse_github_repo(github_url) if github_url else None
        if parsed:
            releases = self.fetch_github_releases(parsed[0], parsed[1], from_version, to_version)

        return {
            "package_name": package_name,
            "normalized_name": normalize_package_name(package_name),
            "from_version": from_version,
            "to_version": to_version,
            "github_url": github_url,
            "releases": releases,
            "version_history": self.fetch_pypi_versions(package_name),
        }

    @staticmethod
    def _github_from_pypi(pypi_info: dict[str, Any]) -> Optional[str]:
        info = pypi_info.get("info") or pypi_info
        urls = info.get("project_urls") or {}
        for val in list(urls.values()) + [info.get("home_page"), info.get("project_url")]:
            if val and "github.com" in str(val).lower():
                return str(val)
        return None
