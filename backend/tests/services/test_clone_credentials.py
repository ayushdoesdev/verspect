"""Regression: GitHub tokens must never persist in .git/config."""

from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo

from app.services.clone import (
    build_authenticated_clone_url,
    extract_token_from_remote_url,
    normalize_public_clone_url,
    scrub_all_clone_credentials,
    scrub_path_remote_credentials,
    scrub_repo_remote_credentials,
    strip_credentials_from_url,
)


def test_strip_credentials_from_https_url() -> None:
    dirty = "https://x-access-token:gho_SECRET123@github.com/acme/repo.git"
    assert strip_credentials_from_url(dirty) == "https://github.com/acme/repo.git"
    assert "gho_SECRET" not in strip_credentials_from_url(dirty)


def test_normalize_ssh_and_auth_urls() -> None:
    assert (
        normalize_public_clone_url("git@github.com:acme/repo.git")
        == "https://github.com/acme/repo.git"
    )
    dirty = build_authenticated_clone_url(
        "https://github.com/acme/repo.git", "gho_SECRET123"
    )
    assert "gho_SECRET123" in dirty
    assert normalize_public_clone_url(dirty) == "https://github.com/acme/repo.git"


def test_extract_token_from_remote_url() -> None:
    url = "https://x-access-token:gho_SECRET123@github.com/acme/repo.git"
    assert extract_token_from_remote_url(url) == "gho_SECRET123"
    assert extract_token_from_remote_url("https://github.com/acme/repo.git") is None


def test_scrub_repo_remote_removes_token(tmp_path: Path) -> None:
    repo = Repo.init(tmp_path)
    dirty = "https://x-access-token:gho_SECRET999@github.com/acme/repo.git"
    repo.create_remote("origin", dirty)
    assert "gho_SECRET999" in next(repo.remotes.origin.urls)

    scrub_repo_remote_credentials(repo, public_url="https://github.com/acme/repo.git")

    clean = next(repo.remotes.origin.urls)
    assert clean == "https://github.com/acme/repo.git"
    assert "gho_SECRET" not in clean
    config_text = (tmp_path / ".git" / "config").read_text()
    assert "gho_SECRET" not in config_text
    assert "x-access-token" not in config_text


def test_scrub_all_clone_credentials_returns_tokens_and_cleans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import clone as clone_mod

    monkeypatch.setattr(clone_mod.settings, "scan_clone_dir", str(tmp_path))
    repo_dir = tmp_path / "aaaa-bbbb"
    repo = Repo.init(repo_dir)
    repo.create_remote(
        "origin",
        "https://x-access-token:gho_ROTATE_ME@github.com/acme/repo.git",
    )

    found = scrub_all_clone_credentials()
    assert found.get("aaaa-bbbb") == "gho_ROTATE_ME"
    assert "gho_ROTATE_ME" not in (repo_dir / ".git" / "config").read_text()
    assert scrub_path_remote_credentials(repo_dir) is True
