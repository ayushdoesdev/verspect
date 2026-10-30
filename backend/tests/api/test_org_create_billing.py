"""Regression: new organizations must not inherit paid subscriptions."""

from __future__ import annotations

import inspect

from app.api.v1 import organizations as org_api


def test_create_organization_source_starts_free_trialing() -> None:
    src = inspect.getsource(org_api.create_organization)
    assert 'plan="free"' in src or "plan='free'" in src
    assert "plan=active.plan" not in src
    assert 'status="active"' not in src and "status='active'" not in src
    assert 'status="trialing"' in src or "status='trialing'" in src
    assert "TRIAL_DAYS" in src


def test_create_organization_does_not_copy_active_plan_into_subscription() -> None:
    src = inspect.getsource(org_api.create_organization)
    # Subscription plan must be literal free, not org.plan after cloning paid
    assert "plan=org.plan" not in src
    assert "Subscription(" in src
