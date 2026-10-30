"""Entitlement resolution — evaluation window and paid access."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services.entitlements import resolve_entitlements
from app.services.plans import TRIAL_DAYS


def _org(plan: str = "free", created_at: datetime | None = None):
    return SimpleNamespace(
        id=uuid4(),
        plan=plan,
        created_at=created_at or datetime.now(timezone.utc),
    )


def _sub(
    *,
    status: str = "trialing",
    trial_ends_at: datetime | None = None,
    plan: str = "free",
):
    return SimpleNamespace(
        status=status,
        trial_ends_at=trial_ends_at,
        plan=plan,
        billing_interval="month",
        seat_count=1,
        current_period_end=None,
        cancel_at_period_end=False,
    )


def test_evaluation_active_within_window():
    now = datetime.now(timezone.utc)
    org = _org(created_at=now - timedelta(days=1))
    sub = _sub(status="trialing", trial_ends_at=now + timedelta(days=6))
    ents = resolve_entitlements(org, sub)
    assert ents.evaluation_active is True
    assert ents.evaluation_expired is False
    assert ents.can_write is True
    assert ents.upgrade_simulator is True
    assert ents.ai_migration_assistant is False
    assert ents.read_only is False


def test_evaluation_expired_read_only():
    now = datetime.now(timezone.utc)
    org = _org(created_at=now - timedelta(days=TRIAL_DAYS + 2))
    sub = _sub(status="trialing", trial_ends_at=now - timedelta(days=1))
    ents = resolve_entitlements(org, sub)
    assert ents.evaluation_expired is True
    assert ents.evaluation_active is False
    assert ents.can_write is False
    assert ents.can_import_repositories is False
    assert ents.can_trigger_scans is False
    assert ents.upgrade_simulator is False
    assert ents.read_only is True
    assert ents.status == "expired"
    # Historical viewing is not gated by these flags
    assert ents.can_view_ai_migration_reports is True


def test_starter_active_has_simulator_not_migration():
    org = _org(plan="starter")
    sub = _sub(status="active", plan="starter", trial_ends_at=None)
    ents = resolve_entitlements(org, sub)
    assert ents.can_write is True
    assert ents.upgrade_simulator is True
    assert ents.ai_enabled is False
    assert ents.ai_migration_assistant is False
    assert ents.evaluation_expired is False


def test_pro_has_advisor_not_migration():
    org = _org(plan="pro")
    sub = _sub(status="active", plan="pro")
    ents = resolve_entitlements(org, sub)
    assert ents.ai_enabled is True
    assert ents.api_access is True
    assert ents.scheduled_scans is True
    assert ents.ai_migration_assistant is False


def test_team_has_migration():
    org = _org(plan="team")
    sub = _sub(status="active", plan="team")
    ents = resolve_entitlements(org, sub)
    assert ents.ai_migration_assistant is True
    assert ents.can_generate_ai_migration is True
    assert ents.teams_enabled is True


def test_enterprise_preserves_ai_and_migration():
    org = _org(plan="enterprise")
    sub = _sub(status="active", plan="enterprise")
    ents = resolve_entitlements(org, sub)
    assert ents.ai_enabled is True
    assert ents.ai_migration_assistant is True
    assert ents.can_generate_ai_migration is True


def test_evaluation_and_starter_do_not_enable_ai():
    now = datetime.now(timezone.utc)
    eval_ents = resolve_entitlements(
        _org(plan="free", created_at=now - timedelta(days=1)),
        _sub(status="trialing", trial_ends_at=now + timedelta(days=6)),
    )
    assert eval_ents.ai_enabled is False
    starter = resolve_entitlements(_org(plan="starter"), _sub(status="active", plan="starter"))
    assert starter.ai_enabled is False


@pytest.mark.asyncio
async def test_require_ai_feature_rejects_plans_without_ai():
    from unittest.mock import AsyncMock, patch

    from fastapi import HTTPException

    from app.services.entitlements import require_ai_feature

    org = _org(plan="starter")
    snapshot = SimpleNamespace(ai_enabled=False, plan="starter")
    with patch("app.services.entitlements.get_entitlements", new=AsyncMock(return_value=snapshot)):
        with pytest.raises(HTTPException) as exc:
            await require_ai_feature(MagicMock(), org=org)
    assert exc.value.status_code == 403
    assert exc.value.detail["feature"] == "ai"


def test_canceled_paid_is_read_only():
    org = _org(plan="pro")
    sub = _sub(status="canceled", plan="pro")
    ents = resolve_entitlements(org, sub)
    assert ents.can_write is False
    assert ents.upgrade_simulator is False
    assert ents.ai_enabled is False
