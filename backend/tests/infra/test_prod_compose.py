"""Regression C8: production compose must not be the development stack."""

from __future__ import annotations

from pathlib import Path

import pytest


def _repo_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "docker-compose.prod.yml").is_file():
            return parent
    return None


ROOT = _repo_root()


@pytest.mark.skipif(ROOT is None, reason="docker-compose.prod.yml not mounted in this environment")
def test_prod_compose_exists() -> None:
    assert ROOT is not None
    assert (ROOT / "docker-compose.prod.yml").is_file()


@pytest.mark.skipif(ROOT is None, reason="docker-compose.prod.yml not mounted in this environment")
def test_prod_compose_is_not_dev_mode() -> None:
    assert ROOT is not None
    text = (ROOT / "docker-compose.prod.yml").read_text()
    assert "--reload" not in text
    assert "npm run dev" not in text
    assert "mailhog" not in text.lower()
    assert "allkeys-lru" not in text
    assert "noeviction" in text
    assert "requirepass" in text
    assert "./backend:/app" not in text
    assert "./frontend:/app" not in text
    assert '"5432:5432"' not in text
    assert '"6379:6379"' not in text


@pytest.mark.skipif(ROOT is None, reason="docker-compose.yml not mounted in this environment")
def test_dev_compose_still_exists_for_local() -> None:
    assert ROOT is not None
    assert (ROOT / "docker-compose.yml").is_file()
    assert (ROOT / "docker-compose.prod.yml").read_text() != (
        ROOT / "docker-compose.yml"
    ).read_text()
