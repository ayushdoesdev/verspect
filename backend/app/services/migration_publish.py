"""Create a GitHub pull request from validated migration patches.

Never runs automatically. Requires explicit confirm=True from the user.
Does not claim migration success — only that a PR was opened with the
validated snippets that could be applied to fetched files.
"""

from __future__ import annotations

import base64
import re
from typing import Any, Optional

from app.core.logging import get_logger
from app.models.dependency import Dependency
from app.models.repository import Repository
from app.models.upgrade_simulation import UpgradeSimulation
from app.services.github import GitHubAPIClient

logger = get_logger(__name__)

_SAFE_BRANCH = re.compile(r"[^a-zA-Z0-9._/-]+")


def apply_snippet(file_content: str, current_code: str, suggested_code: str) -> Optional[str]:
    """Replace the first occurrence of current_code. Returns None if not found."""
    current = (current_code or "").strip("\n")
    suggested = suggested_code or ""
    if not current or current not in file_content:
        return None
    return file_content.replace(current, suggested, 1)


def selectable_patches(suggested_changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Only high-confidence validated automatic replacements."""
    out: list[dict[str, Any]] = []
    for item in suggested_changes or []:
        if not isinstance(item, dict):
            continue
        status = item.get("migration_status")
        suggested = item.get("suggested_code") or ""
        current = item.get("current_code") or ""
        path = item.get("file_path") or ""
        if path.startswith("(") or not suggested.strip():
            continue
        if status and status != "automatic_migration":
            continue
        if item.get("automatic") is False:
            continue
        if not current.strip():
            continue
        out.append(item)
    return out


async def publish_migration_pull_request(
    session: Any,
    *,
    simulation: UpgradeSimulation,
    repository: Repository,
    dependency: Dependency,
    github: GitHubAPIClient,
    confirm: bool,
    actor_login: Optional[str] = None,
) -> dict[str, Any]:
    if not confirm:
        raise ValueError("Explicit confirmation is required to create a GitHub pull request.")
    if simulation.status != "completed":
        raise ValueError("Upgrade analysis must complete before creating a pull request.")

    patches = selectable_patches(list(simulation.suggested_changes or []))
    if not patches:
        raise ValueError(
            "No validated automatic patches are available. Download the diff and apply it manually."
        )

    owner = repository.owner_login
    name = repository.name
    base = repository.default_branch or "main"
    pkg = re.sub(_SAFE_BRANCH, "-", simulation.package_name or "dep").strip("-")[:40]
    branch = f"verspect/migrate-{pkg}-{simulation.from_version}-to-{simulation.to_version}"[:100]

    base_sha = await github.get_default_branch_sha(owner, name, base)
    await github.create_branch(owner, name, branch=branch, from_sha=base_sha)

    applied: list[str] = []
    skipped: list[str] = []
    for patch in patches:
        path = patch["file_path"].lstrip("./")
        try:
            existing = await github.get_file_contents(owner, name, path, ref=branch)
        except Exception:
            skipped.append(f"{path}: file not found on GitHub")
            continue
        encoding = existing.get("encoding")
        raw = existing.get("content") or ""
        if encoding == "base64":
            content = base64.b64decode(raw.replace("\n", "")).decode("utf-8")
        else:
            content = str(raw)
        updated = apply_snippet(content, patch.get("current_code") or "", patch.get("suggested_code") or "")
        if updated is None:
            skipped.append(f"{path}: snippet no longer matches repository contents")
            continue
        sha = existing.get("sha")
        b64 = base64.b64encode(updated.encode("utf-8")).decode("ascii")
        message = (
            f"chore: migrate {simulation.package_name} "
            f"{simulation.from_version} → {simulation.to_version} in {path}"
        )
        await github.put_file(
            owner,
            name,
            path,
            message=message,
            content_b64=b64,
            branch=branch,
            sha=sha,
        )
        applied.append(path)

    if not applied:
        raise ValueError(
            "None of the validated patches matched current GitHub file contents. "
            "The repository may have changed since the scan."
        )

    title = (
        f"chore: migrate {simulation.package_name} "
        f"{simulation.from_version} → {simulation.to_version}"
    )
    body_lines = [
        "This pull request was created by Verspect after **explicit user confirmation**.",
        "",
        f"- Package: `{simulation.package_name}`",
        f"- Current: `{simulation.from_version}`",
        f"- Target: `{simulation.to_version}`",
        f"- Applied files: {len(applied)}",
        f"- Skipped: {len(skipped)}",
        "",
        "Validation: only deterministic/high-confidence automatic replacements were applied.",
        "Review the diff. Do not merge solely because Verspect opened this PR.",
    ]
    if skipped:
        body_lines.append("")
        body_lines.append("Skipped:")
        body_lines.extend(f"- {s}" for s in skipped[:20])
    if actor_login:
        body_lines.append("")
        body_lines.append(f"Requested by GitHub user `{actor_login}`.")

    pr = await github.create_pull_request(
        owner,
        name,
        title=title,
        body="\n".join(body_lines),
        head=branch,
        base=base,
    )
    pr_url = pr.get("html_url")
    sources = dict(simulation.collected_sources or {})
    sources["github_pr_url"] = pr_url
    sources["github_pr_branch"] = branch
    sources["github_pr_applied_files"] = applied
    sources["github_pr_skipped"] = skipped
    simulation.collected_sources = sources
    session.add(simulation)
    session.flush()
    logger.info(
        "migration_pr_created",
        simulation_id=str(simulation.id),
        repository_id=str(repository.id),
        applied=len(applied),
        skipped=len(skipped),
    )
    return {
        "pull_request_url": pr_url,
        "branch": branch,
        "applied_files": applied,
        "skipped": skipped,
        "number": pr.get("number"),
    }
