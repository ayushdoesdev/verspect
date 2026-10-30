"""Collect release notes, changelogs, GitHub releases, and docs for upgrade analysis."""

from __future__ import annotations

from typing import Any, Optional

import httpx
from packaging.version import InvalidVersion, Version

from app.core.logging import get_logger
from app.scanners.normalize import normalize_package_name

logger = get_logger(__name__)


def _parse_version(value: str) -> Optional[Version]:
    raw = (value or "").strip()
    if raw.lower().startswith("v") and raw[1:2].isdigit():
        raw = raw[1:]
    try:
        return Version(raw)
    except InvalidVersion:
        return None


def _in_range(ver: str, from_v: str, to_v: str) -> bool:
    current = _parse_version(ver)
    lo = _parse_version(from_v)
    hi = _parse_version(to_v)
    if not current or not lo or not hi:
        return True
    return lo < current <= hi


class UpgradeSourceCollector:
    """Gather multi-source upgrade intelligence for a package version range."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def collect(
        self,
        package_name: str,
        from_version: str,
        to_version: str,
        github_repo_url: Optional[str] = None,
        existing_releases: Optional[list[dict[str, Any]]] = None,
        cve_summaries: Optional[list[str]] = None,
        ecosystem: str = "PyPI",
        skip_pypi: bool = False,
    ) -> dict[str, Any]:
        name = normalize_package_name(package_name)
        sources: dict[str, Any] = {
            "package_name": package_name,
            "from_version": from_version,
            "to_version": to_version,
            "pypi": {},
            "github_releases": [],
            "release_notes": [],
            "breaking_change_hints": [],
            "deprecated_hints": [],
            "security_fixes": cve_summaries or [],
            "documentation_urls": [],
            "existing_release_analyses": existing_releases or [],
        }

        eco = (ecosystem or "PyPI").lower()
        use_pypi = not skip_pypi and eco in {"pypi", "python", ""}
        pypi: dict[str, Any] = {}
        if use_pypi:
            pypi = self._fetch_pypi(name)
        sources["pypi"] = {
            "summary": (pypi.get("info") or {}).get("summary"),
            "home_page": (pypi.get("info") or {}).get("home_page"),
            "project_urls": (pypi.get("info") or {}).get("project_urls") or {},
            "description_excerpt": ((pypi.get("info") or {}).get("description") or "")[:8000],
        }

        urls = sources["pypi"]["project_urls"] or {}
        for key, url in urls.items():
            if not url:
                continue
            lower_key = key.lower()
            if any(x in lower_key for x in ("changelog", "release", "news", "history")):
                sources["documentation_urls"].append({"type": "changelog", "url": url, "label": key})
            elif any(x in lower_key for x in ("doc", "readthedocs", "documentation")):
                sources["documentation_urls"].append({"type": "docs", "url": url, "label": key})
            elif "github.com" in url.lower() and not github_repo_url:
                github_repo_url = url

        # Prefer GitHub releases between versions
        if github_repo_url:
            owner_repo = self._parse_github_owner_repo(github_repo_url)
            if owner_repo:
                releases = self._fetch_github_releases(*owner_repo)
                for rel in releases:
                    tag = (rel.get("tag_name") or "").lstrip("v")
                    if not tag or not _in_range(tag, from_version, to_version):
                        # Always include exact target tag
                        if tag != to_version and tag != f"v{to_version}":
                            continue
                    body = rel.get("body") or ""
                    sources["github_releases"].append(
                        {
                            "tag": rel.get("tag_name"),
                            "name": rel.get("name"),
                            "published_at": rel.get("published_at"),
                            "url": rel.get("html_url"),
                            "body": body[:12000],
                        }
                    )
                    sources["release_notes"].append(
                        {
                            "version": tag,
                            "source": "github",
                            "text": body[:12000],
                        }
                    )
                    lower = body.lower()
                    if any(k in lower for k in ("breaking", "incompatible", "removed")):
                        sources["breaking_change_hints"].append(f"{tag}: see GitHub release notes")
                    if "deprecat" in lower:
                        sources["deprecated_hints"].append(f"{tag}: deprecations mentioned")
                    if any(k in lower for k in ("security", "cve", "vulnerab")):
                        sources["security_fixes"].append(f"{tag}: security notes in release")

        if github_repo_url and not sources["release_notes"]:
            self._append_github_changelog_files(sources, github_repo_url, from_version, to_version)

        # Pull changelog page excerpt if available
        noted_urls = {n.get("url") for n in sources["release_notes"] if n.get("url")}
        for doc in sources["documentation_urls"][:2]:
            if doc.get("url") in noted_urls:
                continue
            excerpt = self._fetch_text_excerpt(doc["url"])
            if excerpt:
                sources["release_notes"].append(
                    {
                        "version": f"{from_version}..{to_version}",
                        "source": doc["type"],
                        "url": doc["url"],
                        "text": excerpt,
                    }
                )

        # Merge existing AI release analyses already stored
        for er in existing_releases or []:
            if er.get("ai_summary"):
                sources["release_notes"].append(
                    {
                        "version": er.get("version"),
                        "source": "prior_analysis",
                        "text": er.get("ai_summary"),
                    }
                )
            for bc in er.get("breaking_changes") or []:
                sources["breaking_change_hints"].append(str(bc))
            for dep in er.get("deprecated_apis") or []:
                sources["deprecated_hints"].append(str(dep))

        # PyPI description as fallback notes (Python ecosystem only)
        if (
            use_pypi
            and not sources["release_notes"]
            and sources["pypi"].get("description_excerpt")
        ):
            sources["release_notes"].append(
                {
                    "version": to_version,
                    "source": "pypi_description",
                    "text": sources["pypi"]["description_excerpt"],
                }
            )

        return sources

    def _append_github_changelog_files(
        self,
        sources: dict[str, Any],
        github_repo_url: str,
        from_version: str,
        to_version: str,
    ) -> None:
        """When the releases API is empty or rate-limited, try common changelog files."""
        owner_repo = self._parse_github_owner_repo(github_repo_url)
        if not owner_repo:
            return
        owner, repo = owner_repo
        for path in (
            "CHANGELOG.md",
            "CHANGELOG",
            "CHANGES.md",
            "NEWS.md",
            "HISTORY.md",
            "History.md",
        ):
            for branch in ("master", "main"):
                url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
                excerpt = self._fetch_text_excerpt(url, limit=14000)
                if not excerpt:
                    continue
                sources["documentation_urls"].append(
                    {"type": "changelog", "url": url, "label": path}
                )
                sources["release_notes"].append(
                    {
                        "version": f"{from_version}..{to_version}",
                        "source": "changelog",
                        "url": url,
                        "text": excerpt,
                    }
                )
                return

    def _fetch_pypi(self, package_name: str) -> dict[str, Any]:
        url = f"https://pypi.org/pypi/{package_name}/json"
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code == 404:
                    return {}
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.warning("upgrade_source_pypi_failed", package=package_name, error=str(exc))
            return {}

    @staticmethod
    def _parse_github_owner_repo(url: str) -> Optional[tuple[str, str]]:
        # https://github.com/owner/repo or https://github.com/owner/repo.git
        try:
            parts = url.rstrip("/").split("github.com/")[-1].split("/")
            if len(parts) >= 2:
                return parts[0], parts[1].removesuffix(".git")
        except Exception:
            return None
        return None

    def _fetch_github_releases(self, owner: str, repo: str) -> list[dict[str, Any]]:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(
                    url,
                    headers={
                        "Accept": "application/vnd.github+json",
                        "User-Agent": "DependencyIntelligence/1.0",
                    },
                    params={"per_page": 30},
                )
                if resp.status_code != 200:
                    logger.warning(
                        "upgrade_source_github_status",
                        repo=f"{owner}/{repo}",
                        status=resp.status_code,
                    )
                    return []
                data = resp.json()
                return data if isinstance(data, list) else []
        except Exception as exc:
            logger.warning("upgrade_source_github_failed", repo=f"{owner}/{repo}", error=str(exc))
            return []

    def _fetch_text_excerpt(self, url: str, limit: int = 10000) -> Optional[str]:
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": "DependencyIntelligence/1.0"})
                if resp.status_code != 200:
                    return None
                text = resp.text
                # Strip crude HTML tags for AI readability
                if "<html" in text.lower() or "<body" in text.lower():
                    import re

                    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
                    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
                    text = re.sub(r"<[^>]+>", " ", text)
                    text = re.sub(r"\s+", " ", text)
                return text[:limit]
        except Exception:
            return None
