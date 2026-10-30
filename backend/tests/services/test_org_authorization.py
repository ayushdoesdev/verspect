"""Regression: removed members must lose organization access immediately."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.organizations import (
    clear_active_organization_if_match,
    get_active_organization,
)


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_get_active_organization_requires_membership(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    stale_org_id = uuid4()
    personal_id = uuid4()
    user = SimpleNamespace(id=user_id, active_organization_id=stale_org_id)
    personal = SimpleNamespace(id=personal_id, is_personal=True)

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarResult(None))

    async def _ensure(_db, user_arg):
        user_arg.active_organization_id = personal.id
        return personal

    from app.services import organizations as org_mod

    monkeypatch.setattr(org_mod, "ensure_personal_organization", _ensure)
    org = await get_active_organization(db, user)

    assert org.id == personal_id
    assert user.active_organization_id == personal_id


@pytest.mark.asyncio
async def test_get_active_organization_returns_org_when_member() -> None:
    user_id = uuid4()
    org_id = uuid4()
    user = SimpleNamespace(id=user_id, active_organization_id=org_id)
    org = SimpleNamespace(id=org_id)

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarResult(org))

    result = await get_active_organization(db, user)
    assert result is org
    assert user.active_organization_id == org_id


@pytest.mark.asyncio
async def test_clear_active_organization_if_match() -> None:
    user_id = uuid4()
    org_id = uuid4()
    user = SimpleNamespace(id=user_id, active_organization_id=org_id)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarResult(user))

    await clear_active_organization_if_match(db, user_id=user_id, organization_id=org_id)
    assert user.active_organization_id is None

    other = uuid4()
    user.active_organization_id = other
    await clear_active_organization_if_match(db, user_id=user_id, organization_id=org_id)
    assert user.active_organization_id == other
