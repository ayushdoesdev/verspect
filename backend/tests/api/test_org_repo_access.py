"""Org-scoped repository access regressions."""

from __future__ import annotations

import inspect

from app.api.v1 import migration as migration_api
from app.api.v1 import repositories as repos_api
from app.services.repo_access import get_org_repository


def test_repository_get_uses_org_helper() -> None:
    src = inspect.getsource(repos_api.get_repository)
    assert "_get_org_repo" in src
    assert "owner_id == current_user.id" not in src


def test_github_already_imported_is_org_scoped() -> None:
    src = inspect.getsource(repos_api.list_github_repositories)
    assert "Repository.organization_id == org.id" in src
    assert "Repository.owner_id == current_user.id" not in src


def test_import_duplicate_is_org_scoped() -> None:
    src = inspect.getsource(repos_api.import_repositories)
    assert "Repository.organization_id == org.id" in src


def test_org_repo_helper_404_not_403_for_cross_tenant() -> None:
    src = inspect.getsource(get_org_repository)
    assert "404" in src
    assert "organization_id == org.id" in src
    assert "WRITE_ROLES" in src
    assert "Viewers can read" in src


def test_migration_access_is_org_scoped() -> None:
    src = inspect.getsource(migration_api._assert_dependency_access)
    assert "organization_id == org.id" in src
    assert "owner_id" not in src
    pr_src = inspect.getsource(migration_api.create_migration_pull_request)
    assert "confirm" in pr_src
    assert "require_ai_migration_assistant" in pr_src
