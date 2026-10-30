"""Regression H3: scan/dependency APIs scope by active organization membership."""

from __future__ import annotations

import inspect

from app.api.v1 import dependencies as deps_api
from app.api.v1 import scans as scans_api


def test_trigger_scan_uses_organization_not_owner_only() -> None:
    src = inspect.getsource(scans_api.trigger_scan)
    assert "Repository.organization_id == org.id" in src
    assert "Repository.owner_id == current_user.id" not in src


def test_dependency_access_uses_organization() -> None:
    src = inspect.getsource(deps_api._get_owned_dependency)
    assert "Repository.organization_id == org.id" in src
    assert "Repository.owner_id == user_id" not in src
    list_src = inspect.getsource(deps_api.list_dependencies)
    assert "Repository.organization_id == org.id" in list_src


def test_dashboard_and_search_use_organization() -> None:
    from app.api.v1 import dashboard as dash_api
    from app.api.v1 import search as search_api

    assert "organization_id == org.id" in inspect.getsource(dash_api.get_dashboard)
    assert "organization_id == org.id" in inspect.getsource(search_api.search)
