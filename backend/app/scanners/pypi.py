"""PyPI version checker."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from packaging.version import InvalidVersion, Version
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.scanners.normalize import normalize_package_name

logger = get_logger(__name__)

PYPI_JSON_URL = "https://pypi.org/pypi/{package}/json"


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        # PyPI uses ISO format sometimes with Z
        cleaned = value.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def compare_versions(current: str, latest: str) -> dict[str, Any]:
    try:
        c = Version(current)
        l = Version(latest)
    except InvalidVersion:
        return {
            "is_outdated": current != latest,
            "major_behind": 0,
            "minor_behind": 0,
            "patch_behind": 0,
        }
    is_outdated = c < l
    major = max(0, l.major - c.major) if is_outdated else 0
    if l.major == c.major:
        minor = max(0, l.minor - c.minor) if is_outdated else 0
        patch = max(0, l.micro - c.micro) if is_outdated and l.minor == c.minor else 0
    else:
        minor = 0
        patch = 0
    return {
        "is_outdated": is_outdated,
        "major_behind": major,
        "minor_behind": minor,
        "patch_behind": patch,
    }


class PyPIClient:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def get_package_info(self, package_name: str) -> Optional[dict[str, Any]]:
        name = normalize_package_name(package_name)
        url = PYPI_JSON_URL.format(package=name)
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url)
                if response.status_code == 404:
                    logger.warning("pypi_package_not_found", package=name)
                    return None
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            logger.error("pypi_fetch_failed", package=name, error=str(exc))
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

        info = data.get("info") or {}
        latest = info.get("version")
        releases_raw = data.get("releases") or {}
        release_list: list[dict[str, Any]] = []
        for ver, files in releases_raw.items():
            if not files:
                upload = None
            else:
                upload = files[0].get("upload_time_iso_8601") or files[0].get("upload_time")
            yanked = any(f.get("yanked") for f in files) if files else False
            release_list.append(
                {
                    "version": ver,
                    "released_at": _parse_dt(upload),
                    "is_yanked": yanked,
                    "requires_python": (files[0].get("requires_python") if files else None),
                    "download_url": (files[0].get("url") if files else None),
                    "file_size_bytes": (files[0].get("size") if files else None),
                    "checksum_sha256": (
                        (files[0].get("digests") or {}).get("sha256") if files else None
                    ),
                }
            )

        # Sort releases by version when possible
        def sort_key(item: dict) -> Version:
            try:
                return Version(item["version"])
            except InvalidVersion:
                return Version("0")

        release_list.sort(key=sort_key, reverse=True)

        comparison = (
            compare_versions(current_version, latest)
            if current_version and latest
            else {"is_outdated": False, "major_behind": 0, "minor_behind": 0, "patch_behind": 0}
        )

        license_raw = info.get("license") or ""
        classifiers = info.get("classifiers") or []
        license_spdx = None
        for c in classifiers:
            if c.startswith("License ::"):
                license_spdx = c
                break

        urls = info.get("project_urls") or {}
        github_url = None
        for key, val in urls.items():
            if val and "github.com" in val.lower():
                github_url = val
                break

        last_release_at = None
        if latest and latest in releases_raw and releases_raw[latest]:
            last_release_at = _parse_dt(
                releases_raw[latest][0].get("upload_time_iso_8601")
                or releases_raw[latest][0].get("upload_time")
            )

        return {
            "package_name": package_name,
            "normalized_name": normalize_package_name(package_name),
            "latest_version": latest,
            "current_version": current_version,
            "is_outdated": comparison["is_outdated"],
            "major_behind": comparison["major_behind"],
            "minor_behind": comparison["minor_behind"],
            "patch_behind": comparison["patch_behind"],
            "summary": info.get("summary"),
            "home_page": info.get("home_page") or urls.get("Homepage"),
            "pypi_url": info.get("package_url") or f"https://pypi.org/project/{normalize_package_name(package_name)}/",
            "author": info.get("author"),
            "requires_python": info.get("requires_python"),
            "license_raw": license_raw,
            "license_classifier": license_spdx,
            "github_repo_url": github_url,
            "last_release_at": last_release_at,
            "releases": release_list[:50],
            "info": info,
        }


# Simple download stats via pypistats-compatible public API (pepy / pypi)
def fetch_recent_downloads(package_name: str) -> Optional[int]:
    name = normalize_package_name(package_name)
    url = f"https://pypistats.org/api/packages/{name}/recent"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url)
            if response.status_code != 200:
                return None
            data = response.json().get("data") or {}
            return data.get("last_month")
    except Exception:
        return None
