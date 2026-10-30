"""npm registry metadata client."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.scanners.analyzers.javascript import normalize_npm_name
from app.scanners.pypi import compare_versions

logger = get_logger(__name__)
NPM_REGISTRY_URL = "https://registry.npmjs.org/{package}"


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class NpmClient:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def get_package_info(self, package_name: str) -> Optional[dict[str, Any]]:
        name = normalize_npm_name(package_name)
        url = NPM_REGISTRY_URL.format(package=quote(name, safe=""))
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url)
                if response.status_code == 404:
                    logger.warning("npm_package_not_found", package=name)
                    return None
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            logger.error("npm_fetch_failed", package=name, error=str(exc))
            raise

    def extract_version_info(
        self,
        package_name: str,
        current_version: Optional[str] = None,
    ) -> dict[str, Any]:
        data = self.get_package_info(package_name)
        if not data:
            return {
                "package_name": package_name,
                "latest_version": None,
                "current_version": current_version,
                "is_outdated": False,
                "info": {},
                "releases": [],
            }

        dist_tags = data.get("dist-tags") or {}
        latest = dist_tags.get("latest")
        versions = data.get("versions") or {}
        latest_info = versions.get(latest, {}) if latest else {}
        times = data.get("time") or {}
        comparison = (
            compare_versions(current_version, latest)
            if current_version and latest
            else {"is_outdated": False, "major_behind": 0, "minor_behind": 0, "patch_behind": 0}
        )

        releases = [
            {
                "version": version,
                "released_at": _parse_dt(times.get(version)),
                "is_yanked": bool(metadata.get("deprecated")),
                "requires_python": None,
                "download_url": (metadata.get("dist") or {}).get("tarball"),
                "file_size_bytes": None,
                "checksum_sha256": None,
            }
            for version, metadata in versions.items()
        ]
        releases.sort(
            key=lambda item: item["released_at"].timestamp() if item["released_at"] else 0.0,
            reverse=True,
        )

        repository = latest_info.get("repository") or data.get("repository") or {}
        repository_url = repository.get("url") if isinstance(repository, dict) else repository
        if isinstance(repository_url, str):
            repository_url = repository_url.removeprefix("git+").removesuffix(".git")
        homepage = latest_info.get("homepage") or data.get("homepage")
        license_value = latest_info.get("license") or data.get("license") or ""
        if isinstance(license_value, dict):
            license_value = license_value.get("type") or ""
        author = latest_info.get("author") or data.get("author")
        if isinstance(author, dict):
            author = author.get("name") or author.get("email")

        return {
            "package_name": package_name,
            "normalized_name": normalize_npm_name(package_name),
            "latest_version": latest,
            "current_version": current_version,
            **comparison,
            "summary": latest_info.get("description") or data.get("description"),
            "home_page": homepage,
            "pypi_url": f"https://www.npmjs.com/package/{quote(normalize_npm_name(package_name), safe='@/')}",
            "author": author,
            "requires_python": None,
            "license_raw": str(license_value),
            "license_classifier": None,
            "github_repo_url": repository_url if repository_url and "github.com" in repository_url else None,
            "last_release_at": _parse_dt(times.get(latest)) if latest else None,
            "releases": releases[:50],
            "info": latest_info,
        }
