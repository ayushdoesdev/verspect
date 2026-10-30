"""Subscription lifecycle — upgrade / downgrade / cancel / reactivate / soft limits."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.billing.lifecycle import (
    PLAN_RANK,
    classify_change,
    clear_pending_change,
    schedule_pending_change,
)
from app.services.billing.soft_limits import count_active_repositories, enforce_repository_soft_limit
from app.services.entitlements import resolve_entitlements
from app.services.plans import get_plan_limits


def test_plan_rank_ladder():
    assert PLAN_RANK["free"] < PLAN_RANK["starter"] < PLAN_RANK["pro"] < PLAN_RANK["team"]


@pytest.mark.parametrize(
    "current,target,kind",
    [
        ("free", "starter", "upgrade"),
        ("starter", "pro", "upgrade"),
        ("pro", "team", "upgrade"),
        ("team", "starter", "downgrade"),
        ("starter", "free", "cancel"),
        ("team", "free", "cancel"),
        ("pro", "pro", "same"),
    ],
)
def test_classify_change(current, target, kind):
    assert classify_change(current, target) == kind


def _org(plan="team", **kwargs):
    base = dict(
        id=uuid4(),
        plan=plan,
        created_at=datetime.now(timezone.utc),
        billing_provider="local",
        billing_customer_id=None,
        stripe_customer_id=None,
        owner_user_id=uuid4(),
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def _sub(**kwargs):
    now = datetime.now(timezone.utc)
    base = dict(
        plan="team",
        status="active",
        trial_ends_at=None,
        billing_interval="month",
        seat_count=1,
        current_period_start=now - timedelta(days=10),
        current_period_end=now + timedelta(days=20),
        cancel_at_period_end=False,
        pending_plan=None,
        pending_interval=None,
        pending_change_type=None,
        pending_change_effective_at=None,
        provider_subscription_id=None,
        stripe_subscription_id=None,
        billing_provider="local",
        extra_metadata={},
        canceled_at=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_cancel_at_period_end_keeps_paid_entitlements():
    org = _org(plan="team")
    sub = _sub(plan="team", cancel_at_period_end=True, pending_plan="free")
    snap = resolve_entitlements(org, sub)
    assert snap.can_write is True
    assert snap.ai_migration_assistant is True
    assert snap.plan == "team"


def test_evaluation_after_cancel_is_read_only_when_expired():
    org = _org(plan="free", created_at=datetime.now(timezone.utc) - timedelta(days=30))
    sub = _sub(plan="free", status="canceled", trial_ends_at=datetime.now(timezone.utc) - timedelta(days=1))
    snap = resolve_entitlements(org, sub)
    assert snap.evaluation_expired is True
    assert snap.read_only is True
    assert snap.can_generate_ai_migration is False
    assert snap.can_view_ai_migration_reports is True


def test_upgrade_ladder_unlocks_features():
    for plan, expect_ai, expect_migration, expect_api in [
        ("free", False, False, False),
        ("starter", False, False, False),
        ("pro", True, False, True),
        ("team", True, True, True),
    ]:
        org = _org(plan=plan)
        # free needs active evaluation window
        if plan == "free":
            org.created_at = datetime.now(timezone.utc)
            sub = _sub(
                plan="free",
                status="trialing",
                trial_ends_at=datetime.now(timezone.utc) + timedelta(days=5),
            )
        else:
            sub = _sub(plan=plan, status="active")
        snap = resolve_entitlements(org, sub)
        assert snap.ai_enabled is expect_ai, plan
        assert snap.can_generate_ai_migration is expect_migration, plan
        assert snap.api_access is expect_api, plan


def test_schedule_and_clear_pending_helpers():
    sub = _sub()
    when = datetime.now(timezone.utc) + timedelta(days=14)
    schedule_pending_change(
        sub, plan="starter", interval="month", change_type="downgrade", effective_at=when
    )
    assert sub.pending_plan == "starter"
    assert sub.pending_change_type == "downgrade"
    clear_pending_change(sub)
    assert sub.pending_plan is None
    assert sub.pending_change_type is None


@pytest.mark.asyncio
async def test_soft_limit_archives_excess_repos(monkeypatch):
    """Team→Starter style shrink archives oldest active repos; never deletes."""
    org = _org(plan="starter")
    repos = []
    for i in range(15):
        repos.append(
            SimpleNamespace(
                id=uuid4(),
                organization_id=org.id,
                owner_id=org.owner_user_id,
                is_archived=False,
                archived_at=None,
                is_watching=True,
                sync_status="idle",
                full_name=f"acme/repo-{i}",
                created_at=datetime.now(timezone.utc) - timedelta(days=15 - i),
                deleted_at=None,
                extra_metadata=None,
            )
        )

    class FakeResult:
        def __init__(self, items):
            self._items = items

        def scalars(self):
            return self

        def all(self):
            return self._items

    class FakeDB:
        def __init__(self):
            self.archived = []

        async def execute(self, _q):
            active = [r for r in repos if not r.is_archived]
            return FakeResult(active)

        async def scalar(self, _q):
            return len([r for r in repos if not r.is_archived])

        async def flush(self):
            return None

    async def fake_archive(db, repo, *, actor, plan, reason=None):
        repo.is_archived = True
        db.archived.append(repo.id)
        return repo

    monkeypatch.setattr(
        "app.services.billing.soft_limits.lifecycle.archive_repository",
        fake_archive,
    )

    db = FakeDB()
    archived = await enforce_repository_soft_limit(db, org, actor=None)
    assert len(archived) == 5  # 15 → 10 starter
    assert sum(1 for r in repos if not r.is_archived) == 10
    # Newest kept
    assert repos[-1].is_archived is False
    assert repos[0].is_archived is True


def test_starter_limits_block_features():
    limits = get_plan_limits("starter")
    assert limits.max_repositories == 10
    assert limits.ai_migration_assistant is False
    assert limits.api_access is False
    assert limits.scheduled_scans is False
    assert limits.webhooks is False


def test_team_limits_enable_migration_and_orgs():
    limits = get_plan_limits("team")
    assert limits.ai_migration_assistant is True
    assert limits.teams_enabled is True
    assert limits.audit_logs is True
    assert limits.max_repositories is None


@pytest.mark.asyncio
async def test_lifecycle_upgrade_local(monkeypatch):
    from app.services.billing import lifecycle as lc

    org = _org(plan="free")
    sub = _sub(plan="free", status="trialing")
    calls = {}

    async def fake_get_or_create(db, o):
        return sub

    async def fake_activate(db, o, **kwargs):
        o.plan = kwargs["plan"]
        sub.plan = kwargs["plan"]
        sub.status = "active"
        calls["activated"] = kwargs["plan"]
        return sub

    monkeypatch.setattr(lc, "get_or_create_subscription", fake_get_or_create)
    monkeypatch.setattr(lc, "activate_plan_local", fake_activate)
    monkeypatch.setattr(
        lc,
        "get_billing_provider",
        lambda: SimpleNamespace(
            name="stripe",
            is_configured=lambda: False,
        ),
    )

    class DB:
        async def flush(self):
            return None

        async def refresh(self, _):
            return None

    result = await lc.change_plan(DB(), org=org, target_plan="starter", interval="month")
    assert result.action == "upgraded"
    assert org.plan == "starter"
    assert calls["activated"] == "starter"


@pytest.mark.asyncio
async def test_production_rejects_local_paid_activation(monkeypatch):
    """Direct /change-plan must not grant Starter/Pro/Team without a billing provider."""
    from app.services.billing import lifecycle as lc
    from app.services.billing.base import BillingNotConfigured

    org = _org(plan="free")
    sub = _sub(plan="free", status="trialing")

    async def fake_get_or_create(db, o):
        return sub

    async def fake_activate(db, o, **kwargs):
        o.plan = kwargs["plan"]
        return sub

    monkeypatch.setattr(lc, "get_or_create_subscription", fake_get_or_create)
    monkeypatch.setattr(lc, "activate_plan_local", fake_activate)
    monkeypatch.setattr(lc, "get_settings", lambda: SimpleNamespace(is_production=True))
    monkeypatch.setattr(
        lc,
        "get_billing_provider",
        lambda: SimpleNamespace(name="stripe", is_configured=lambda: False),
    )

    class DB:
        async def flush(self):
            return None

        async def refresh(self, _):
            return None

    with pytest.raises(BillingNotConfigured):
        await lc.change_plan(DB(), org=org, target_plan="team", interval="month")
    assert org.plan == "free"


@pytest.mark.asyncio
async def test_lifecycle_downgrade_schedules(monkeypatch):
    from app.services.billing import lifecycle as lc

    org = _org(plan="team")
    end = datetime.now(timezone.utc) + timedelta(days=20)
    sub = _sub(plan="team", current_period_end=end)

    async def fake_get_or_create(db, o):
        return sub

    monkeypatch.setattr(lc, "get_or_create_subscription", fake_get_or_create)
    monkeypatch.setattr(
        lc,
        "get_billing_provider",
        lambda: SimpleNamespace(name="razorpay", is_configured=lambda: False),
    )

    class DB:
        async def flush(self):
            return None

        async def refresh(self, _):
            return None

    result = await lc.change_plan(DB(), org=org, target_plan="starter", interval="month")
    assert result.action == "downgrade_scheduled"
    assert org.plan == "team"  # still Team until renewal
    assert sub.pending_plan == "starter"
    assert sub.pending_change_type == "downgrade"
    assert "Team" in result.message and "Starter" in result.message


@pytest.mark.asyncio
async def test_lifecycle_cancel_and_reactivate(monkeypatch):
    from app.services.billing import lifecycle as lc

    org = _org(plan="pro")
    end = datetime.now(timezone.utc) + timedelta(days=12)
    sub = _sub(plan="pro", current_period_end=end)

    async def fake_get_or_create(db, o):
        return sub

    monkeypatch.setattr(lc, "get_or_create_subscription", fake_get_or_create)
    monkeypatch.setattr(
        lc,
        "get_billing_provider",
        lambda: SimpleNamespace(name="stripe", is_configured=lambda: False),
    )

    class DB:
        async def flush(self):
            return None

    cancel_result = await lc.cancel_subscription(DB(), org=org)
    assert cancel_result.action == "cancel_scheduled"
    assert org.plan == "pro"
    assert sub.cancel_at_period_end is True
    assert sub.pending_plan == "free"

    react = await lc.reactivate_subscription(DB(), org=org)
    assert react.action == "reactivated"
    assert sub.cancel_at_period_end is False
    assert sub.pending_plan is None
    assert org.plan == "pro"


@pytest.mark.asyncio
async def test_apply_due_downgrade_enforces_soft_limits(monkeypatch):
    from app.services.billing import lifecycle as lc

    org = _org(plan="team")
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    sub = _sub(
        plan="team",
        pending_plan="starter",
        pending_change_type="downgrade",
        pending_change_effective_at=past,
        pending_interval="month",
    )

    async def fake_select_sub(db, o):
        return sub

    monkeypatch.setattr(
        lc,
        "get_billing_provider",
        lambda: SimpleNamespace(name="local", is_configured=lambda: False),
    )

    soft = {}

    async def fake_soft(db, o, actor=None):
        soft["ran"] = True
        soft["plan"] = o.plan
        return {"archived_repository_ids": ["x"]}

    monkeypatch.setattr(lc, "enforce_plan_soft_limits", fake_soft)

    class FakeScalars:
        def __init__(self, val):
            self.val = val

        def scalar_one_or_none(self):
            return self.val

    class DB:
        async def execute(self, q):
            # first call: select Subscription
            return FakeScalars(sub)

        async def flush(self):
            return None

    # Patch apply path: get sub via execute
    result = await lc.apply_due_pending_changes(DB(), org=org)
    assert result is not None
    assert result.action == "downgraded"
    assert org.plan == "starter"
    assert soft["ran"] is True
    assert soft["plan"] == "starter"


def test_provider_update_signature_accepts_schedule(monkeypatch):
    """Both Stripe and Razorpay expose schedule_change_at on update_subscription."""
    import inspect
    from app.services.billing.stripe_provider import StripeProvider
    from app.services.billing.razorpay_provider import RazorpayProvider

    for cls in (StripeProvider, RazorpayProvider):
        sig = inspect.signature(cls.update_subscription)
        assert "schedule_change_at" in sig.parameters
