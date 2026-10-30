"""Repository clone / sync helpers using GitPython.

Credentials may be used transiently for fetch/clone, but must never remain in
``.git/config`` (or any other on-disk git metadata).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlsplit, urlunsplit

from git import Repo
from git.exc import GitCommandError

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_CRED_IN_URL_RE = re.compile(
    r"^(https?://)(?:[^/@]+@)",
    re.IGNORECASE,
)


def repo_local_path(repository_id: str) -> Path:
    base = Path(settings.scan_clone_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / str(repository_id)


def normalize_public_clone_url(clone_url: str) -> str:
    """Return a credential-free HTTPS (or original non-HTTP) clone URL."""
    url = (clone_url or "").strip()
    if url.startswith("git@"):
        # git@github.com:owner/repo.git -> https://github.com/owner/repo.git
        path = url.split(":", 1)[1]
        url = f"https://github.com/{path}"
    return strip_credentials_from_url(url)


def strip_credentials_from_url(url: str) -> str:
    """Remove userinfo (including x-access-token) from a URL."""
    if not url:
        return url
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return _CRED_IN_URL_RE.sub(r"\1", url)
    if "@" not in parts.netloc:
        return url
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))


def build_authenticated_clone_url(clone_url: str, token: str) -> str:
    """Build a transient authenticated HTTPS URL (never persist the result)."""
    public = normalize_public_clone_url(clone_url)
    if public.startswith("https://"):
        rest = public.removeprefix("https://")
        return f"https://x-access-token:{quote(token, safe='')}@{rest}"
    return public


def extract_token_from_remote_url(url: str) -> Optional[str]:
    """Best-effort extract of an embedded token for revocation/scrubbing."""
    parts = urlsplit(url or "")
    if not parts.password and not parts.username:
        return None
    # https://x-access-token:TOKEN@host  → password is token
    if parts.password:
        return parts.password
    if parts.username and parts.username not in {"x-access-token", "oauth2", "git"}:
        return parts.username
    return None


def scrub_repo_remote_credentials(repo: Repo, *, public_url: Optional[str] = None) -> None:
    """Ensure origin (and all remotes) use credential-free URLs."""
    for remote in repo.remotes:
        try:
            current = next(remote.urls)
        except StopIteration:
            continue
        clean = normalize_public_clone_url(public_url or current)
        if current != clean:
            remote.set_url(clean)
            logger.info("repo_remote_credentials_scrubbed", remote=remote.name)


def scrub_path_remote_credentials(path: Path, *, public_url: Optional[str] = None) -> bool:
    """Scrub credentials from an on-disk clone. Returns True if a repo was scrubbed."""
    if not path.exists() or not (path / ".git").exists():
        return False
    repo = Repo(str(path))
    scrub_repo_remote_credentials(repo, public_url=public_url)
    return True


def scrub_all_clone_credentials() -> dict[str, str]:
    """
    Scrub every clone under scan_clone_dir.

    Returns mapping of repository_id -> extracted token (for revocation).
    Tokens are returned to the caller; they are never logged.
    """
    base = Path(settings.scan_clone_dir)
    found: dict[str, str] = {}
    if not base.exists():
        return found
    for child in base.iterdir():
        if not child.is_dir() or not (child / ".git").exists():
            continue
        try:
            repo = Repo(str(child))
            for remote in repo.remotes:
                for url in remote.urls:
                    token = extract_token_from_remote_url(url)
                    if token and child.name not in found:
                        found[child.name] = token
            scrub_repo_remote_credentials(repo)
        except Exception as exc:  # noqa: BLE001
            logger.warning("repo_scrub_failed", path=str(child), error=str(exc))
    return found


def clone_or_update_repository(
    repository_id: str,
    clone_url: str,
    branch: str,
    token: Optional[str] = None,
) -> tuple[Path, str]:
    """
    Clone repository (or fetch+reset if present).
    Returns (local_path, head_sha).

    Authenticated URLs are used only for the network operation and are scrubbed
    from ``.git/config`` before returning (including on failure after a partial clone).
    """
    path = repo_local_path(repository_id)
    public_url = normalize_public_clone_url(clone_url)
    auth_url = build_authenticated_clone_url(public_url, token) if token else public_url

    if path.exists() and (path / ".git").exists():
        repo = Repo(str(path))
        try:
            origin = repo.remotes.origin
            try:
                if token:
                    origin.set_url(auth_url)
                origin.fetch(prune=True)
                remote_refs = {ref.name for ref in origin.refs}
                target = f"origin/{branch}"
                if target not in remote_refs and "origin/HEAD" in remote_refs:
                    target = "origin/HEAD"
                    branch = repo.git.rev_parse("--abbrev-ref", "origin/HEAD").removeprefix(
                        "origin/"
                    )
                repo.git.checkout("-B", branch, target)
                repo.git.reset("--hard", target)
                sha = repo.head.commit.hexsha
                logger.info("repo_updated", path=str(path), sha=sha)
                return path, sha
            finally:
                scrub_repo_remote_credentials(repo, public_url=public_url)
        except Exception as exc:
            scrub_repo_remote_credentials(repo, public_url=public_url)
            logger.warning("repo_update_failed_recloning", error=str(exc))

    if path.exists():
        shutil.rmtree(path, ignore_errors=True)

    path.parent.mkdir(parents=True, exist_ok=True)
    repo: Optional[Repo] = None
    try:
        try:
            repo = Repo.clone_from(
                auth_url,
                str(path),
                branch=branch,
                depth=1,
                single_branch=True,
            )
        except GitCommandError:
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
            repo = Repo.clone_from(
                auth_url,
                str(path),
                depth=1,
                single_branch=True,
            )
        scrub_repo_remote_credentials(repo, public_url=public_url)
        sha = repo.head.commit.hexsha
        logger.info("repo_cloned", path=str(path), sha=sha)
        return path, sha
    except Exception:
        if path.exists() and (path / ".git").exists():
            try:
                scrub_path_remote_credentials(path, public_url=public_url)
            except Exception:  # noqa: BLE001
                pass
        raise


def cleanup_repository(repository_id: str) -> None:
    path = repo_local_path(repository_id)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
        logger.info("repo_cleaned", path=str(path))
