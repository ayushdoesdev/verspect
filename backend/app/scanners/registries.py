"""Non-PyPI package registry clients (deterministic metadata only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import quote

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.scanners.pypi import compare_versions

logger = get_logger(__name__)

_HEADERS = {"User-Agent": "Verspect-DependencyIntelligence/1.0"}


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _empty(package_name: str, current_version: Optional[str], status: str) -> dict[str, Any]:
    return {
        "package_name": package_name,
        "latest_version": None,
        "current_version": current_version,
        "is_outdated": False,
        "major_behind": 0,
        "minor_behind": 0,
        "patch_behind": 0,
        "releases": [],
        "license_raw": None,
        "license_classifier": None,
        "metadata_status": status,
    }


class CratesIoClient:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def get_package_info(self, package_name: str) -> Optional[dict[str, Any]]:
        url = f"https://crates.io/api/v1/crates/{quote(package_name, safe='')}"
        with httpx.Client(timeout=self.timeout, headers=_HEADERS, follow_redirects=True) as client:
            response = client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    def extract_version_info(
        self, package_name: str, current_version: Optional[str] = None
    ) -> dict[str, Any]:
        try:
            data = self.get_package_info(package_name)
        except httpx.HTTPError as exc:
            logger.warning("crates_fetch_failed", package=package_name, error=str(exc))
            return _empty(package_name, current_version, "crates.io_registry_unavailable")
        if not data:
            return _empty(package_name, current_version, "crates.io_package_not_found")
        crate = data.get("crate") or {}
        latest = crate.get("max_stable_version") or crate.get("newest_version")
        versions = data.get("versions") or []
        latest_row = next((v for v in versions if v.get("num") == latest), versions[0] if versions else {})
        comparison = (
            compare_versions(current_version, latest)
            if current_version and latest
            else {"is_outdated": False, "major_behind": 0, "minor_behind": 0, "patch_behind": 0}
        )
        releases = []
        for v in versions[:30]:
            releases.append(
                {
                    "version": v.get("num"),
                    "released_at": _parse_dt(v.get("created_at")),
                    "is_yanked": bool(v.get("yanked")),
                }
            )
        result = {
            "package_name": package_name,
            "latest_version": latest,
            "current_version": current_version,
            "license_raw": latest_row.get("license"),
            "home_page": crate.get("homepage") or crate.get("repository"),
            "summary": crate.get("description"),
            "github_repo_url": crate.get("repository"),
            "last_release_at": _parse_dt(latest_row.get("created_at")),
            "releases": releases,
            **comparison,
        }
        recent = crate.get("recent_downloads")
        if recent is not None:
            result["download_count_month"] = recent
        return result


class PackagistClient:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def get_package_info(self, package_name: str) -> Optional[dict[str, Any]]:
        url = f"https://repo.packagist.org/p2/{quote(package_name, safe='/')}.json"
        with httpx.Client(timeout=self.timeout, headers=_HEADERS, follow_redirects=True) as client:
            response = client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    def extract_version_info(
        self, package_name: str, current_version: Optional[str] = None
    ) -> dict[str, Any]:
        try:
            data = self.get_package_info(package_name)
        except httpx.HTTPError as exc:
            logger.warning("packagist_fetch_failed", package=package_name, error=str(exc))
            return _empty(package_name, current_version, "packagist_registry_unavailable")
        if not data:
            return _empty(package_name, current_version, "packagist_package_not_found")
        packages = (data.get("packages") or {}).get(package_name) or []
        stable = [
            p
            for p in packages
            if not str(p.get("version") or "").startswith("dev-")
            and "dev" not in str(p.get("version") or "")
        ]
        latest_pkg = stable[0] if stable else (packages[0] if packages else {})
        latest = (latest_pkg.get("version") or "").lstrip("v") or None
        licenses = latest_pkg.get("license") or []
        license_raw = licenses[0] if licenses else None
        comparison = (
            compare_versions(current_version, latest)
            if current_version and latest
            else {"is_outdated": False, "major_behind": 0, "minor_behind": 0, "patch_behind": 0}
        )
        return {
            "package_name": package_name,
            "latest_version": latest,
            "current_version": current_version,
            "license_raw": license_raw,
            "home_page": latest_pkg.get("homepage"),
            "summary": latest_pkg.get("description"),
            "last_release_at": _parse_dt(latest_pkg.get("time")),
            "releases": [
                {"version": (p.get("version") or "").lstrip("v"), "released_at": _parse_dt(p.get("time"))}
                for p in packages[:30]
            ],
            **comparison,
        }


class RubyGemsClient:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def get_package_info(self, package_name: str) -> Optional[dict[str, Any]]:
        url = f"https://rubygems.org/api/v1/gems/{quote(package_name, safe='')}.json"
        with httpx.Client(timeout=self.timeout, headers=_HEADERS, follow_redirects=True) as client:
            response = client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    def extract_version_info(
        self, package_name: str, current_version: Optional[str] = None
    ) -> dict[str, Any]:
        try:
            data = self.get_package_info(package_name)
        except httpx.HTTPError as exc:
            logger.warning("rubygems_fetch_failed", package=package_name, error=str(exc))
            return _empty(package_name, current_version, "rubygems_registry_unavailable")
        if not data:
            return _empty(package_name, current_version, "rubygems_package_not_found")
        latest = data.get("version")
        licenses = data.get("licenses") or []
        comparison = (
            compare_versions(current_version, latest)
            if current_version and latest
            else {"is_outdated": False, "major_behind": 0, "minor_behind": 0, "patch_behind": 0}
        )
        return {
            "package_name": package_name,
            "latest_version": latest,
            "current_version": current_version,
            "license_raw": licenses[0] if licenses else None,
            "home_page": data.get("homepage_uri") or data.get("project_uri"),
            "summary": data.get("info"),
            "github_repo_url": data.get("source_code_uri"),
            "download_count_month": data.get("downloads"),
            "releases": [],
            **comparison,
        }


class MavenCentralClient:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def get_package_info(self, package_name: str) -> Optional[dict[str, Any]]:
        if ":" not in package_name:
            return None
        group, artifact = package_name.split(":", 1)
        q = f"g:{group} AND a:{artifact}"
        url = "https://search.maven.org/solrsearch/select"
        with httpx.Client(timeout=self.timeout, headers=_HEADERS, follow_redirects=True) as client:
            response = client.get(url, params={"q": q, "rows": 1, "wt": "json"})
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    def extract_version_info(
        self, package_name: str, current_version: Optional[str] = None
    ) -> dict[str, Any]:
        try:
            data = self.get_package_info(package_name)
        except httpx.HTTPError as extra:
            logger.warning("maven_fetch_failed", package=package_name, error=str(extra))
            return _empty(package_name, current_version, "maven_registry_unavailable")
        docs = (((data or {}).get("response") or {}).get("docs") or []) if data else []
        if not docs:
            return _empty(package_name, current_version, "maven_package_not_found")
        doc = docs[0]
        latest = doc.get("latestVersion")
        ts = doc.get("timestamp")
        last_release = None
        if isinstance(ts, (int, float)):
            last_release = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
        comparison = (
            compare_versions(current_version, latest)
            if current_version and latest
            else {"is_outdated": False, "major_behind": 0, "minor_behind": 0, "patch_behind": 0}
        )
        return {
            "package_name": package_name,
            "latest_version": latest,
            "current_version": current_version,
            "home_page": None,
            "summary": None,
            "last_release_at": last_release,
            "releases": [],
            **comparison,
        }
