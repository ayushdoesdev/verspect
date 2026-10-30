"""Metadata client for Go modules via proxy.golang.org."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote

import httpx

from app.core.logging import get_logger
from app.scanners.pypi import compare_versions


logger = get_logger(__name__)
GO_PROXY_LATEST_URL = "https://proxy.golang.org/{module}/@latest"


def _escape_module_path(module: str) -> str:
    """Apply the uppercase escaping required by the Go module proxy protocol."""
    escaped = "".join(f"!{char.lower()}" if char.isupper() else char for char in module.strip())
    return quote(escaped, safe="/")


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class GoModulesClient:
    """Fetch latest-version metadata without inventing unavailable fields."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def get_latest(self, module_name: str) -> Optional[dict[str, Any]]:
        url = GO_PROXY_LATEST_URL.format(module=_escape_module_path(module_name))
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url)
                if response.status_code in {404, 410}:
                    logger.warning("go_module_not_found", module=module_name)
                    return None
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Go enrichment is optional. Returning None preserves OSV scanning and
            # explicitly leaves latest_version unavailable.
            logger.warning("go_module_fetch_failed", module=module_name, error=str(exc))
            return None

    def extract_version_info(
        self,
        package_name: str,
        current_version: Optional[str] = None,
    ) -> dict[str, Any]:
        data = self.get_latest(package_name)
        latest = str(data.get("Version")) if data and data.get("Version") else None
        comparison = (
            compare_versions(current_version.removeprefix("v"), latest.removeprefix("v"))
            if current_version and latest
            else {
                "is_outdated": False,
                "major_behind": 0,
                "minor_behind": 0,
                "patch_behind": 0,
            }
        )
        return {
            "package_name": package_name,
            "latest_version": latest,
            "current_version": current_version,
            **comparison,
            "summary": None,
            "home_page": f"https://pkg.go.dev/{package_name}",
            "pypi_url": None,
            "author": None,
            "requires_python": None,
            "license_raw": None,
            "license_classifier": None,
            "github_repo_url": (
                f"https://{package_name}"
                if package_name.startswith("github.com/")
                else None
            ),
            "last_release_at": _parse_time(data.get("Time")) if data else None,
            "releases": [],
            "info": data or {},
            "metadata_status": "available" if data else "latest_unavailable",
        }
