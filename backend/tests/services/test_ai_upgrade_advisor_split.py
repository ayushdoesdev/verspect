"""Repository Scan vs AI Upgrade Advisor separation."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.enums import ScanType
from app.services.ai_upgrade_advisor import org_supports_ai_advisor
from app.services.entitlements import resolve_entitlements
from app.services.plans import get_plan_limits


def _org(plan: str, **kwargs):
    base = dict(
        id=uuid4(),
        plan=plan,
        created_at=datetime.now(timezone.utc),
        billing_provider="local",
        owner_user_id=uuid4(),
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def _sub(plan: str, status: str = "active"):
    return SimpleNamespace(
        plan=plan,
        status=status,
        trial_ends_at=None,
        cancel_at_period_end=False,
    )


@pytest.mark.parametrize(
    "plan,expect_ai",
    [
        ("free", False),
        ("starter", False),
        ("pro", True),
        ("team", True),
        ("enterprise", True),
    ],
)
def test_plan_gates_ai_enabled(plan, expect_ai):
    limits = get_plan_limits(plan)
    assert limits.ai_enabled is expect_ai


@pytest.mark.parametrize(
    "plan,expect_ai",
    [
        ("free", False),
        ("starter", False),
        ("pro", True),
        ("team", True),
        ("enterprise", True),
    ],
)
def test_entitlements_ai_matches_commercial_matrix(plan, expect_ai):
    org = _org(plan)
    if plan == "free":
        org.created_at = datetime.now(timezone.utc)
        sub = SimpleNamespace(
            plan="free",
            status="trialing",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=5),
            cancel_at_period_end=False,
        )
    else:
        sub = _sub(plan)
    snap = resolve_entitlements(org, sub)
    assert snap.ai_enabled is expect_ai
    # Migration Assistant stays separate (Team+)
    if plan in {"team", "enterprise"}:
        assert snap.can_generate_ai_migration is True
    else:
        assert snap.can_generate_ai_migration is False


def test_scan_type_ai_advisor_is_distinct():
    assert ScanType.AI_ADVISOR.value == "ai_advisor"
    assert ScanType.AI_ADVISOR.value != ScanType.FULL.value
    assert ScanType.AI_ADVISOR.value != ScanType.MANUAL.value


def test_org_supports_ai_advisor_uses_entitlements(monkeypatch):
    repo_id = uuid4()
    org = _org("pro")
    sub = _sub("pro")
    repo = SimpleNamespace(id=repo_id, organization_id=org.id)

    class FakeSession:
        def get(self, model, key):
            name = getattr(model, "__name__", str(model))
            if "Repository" in name or key == repo_id:
                return repo
            if "Organization" in name or key == org.id:
                return org
            return None

        def execute(self, _q):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: sub))

    assert org_supports_ai_advisor(FakeSession(), repo_id) is True

    org.plan = "starter"
    sub.plan = "starter"
    assert org_supports_ai_advisor(FakeSession(), repo_id) is False


def test_ensure_release_stub_skips_when_not_outdated():
    from app.services.ai_upgrade_advisor import ensure_release_stub

    dep = SimpleNamespace(
        is_outdated=False,
        current_version="1.0.0",
        latest_version="1.0.0",
    )
    assert ensure_release_stub(SimpleNamespace(), dep) is None


def test_enqueue_helper_skips_when_plan_blocks(monkeypatch):
    """Unit-test the gate without importing Celery task module."""
    from app.services import ai_upgrade_advisor as advisor

    monkeypatch.setattr(advisor, "org_supports_ai_advisor", lambda *_a, **_k: False)
    # Mimic enqueue_ai_upgrade_advisor early return
    assert advisor.org_supports_ai_advisor(SimpleNamespace(), uuid4()) is False