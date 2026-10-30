"""Billing provider factory + provider-neutral sync."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.billing.base import NormalizedSubscription
from app.services.billing.factory import (
    SUPPORTED_PROVIDERS,
    BillingProviderFactory,
    get_billing_provider,
)
from app.services.billing.razorpay_provider import RazorpayProvider
from app.services.billing.stripe_provider import StripeProvider
from app.services.billing.sync import set_customer_ids, set_subscription_provider_ids
from app.services.entitlements import resolve_entitlements


def test_supported_providers():
    assert "stripe" in SUPPORTED_PROVIDERS
    assert "razorpay" in SUPPORTED_PROVIDERS


def test_factory_defaults_to_stripe(monkeypatch):
    monkeypatch.setattr(
        "app.services.billing.factory.get_settings",
        lambda: SimpleNamespace(billing_provider="stripe"),
    )
    provider = get_billing_provider()
    assert isinstance(provider, StripeProvider)
    assert provider.name == "stripe"


def test_factory_selects_razorpay(monkeypatch):
    monkeypatch.setattr(
        "app.services.billing.factory.get_settings",
        lambda: SimpleNamespace(billing_provider="razorpay"),
    )
    provider = BillingProviderFactory.create()
    assert isinstance(provider, RazorpayProvider)
    assert provider.name == "razorpay"


def test_factory_unknown_falls_back_to_stripe(monkeypatch):
    monkeypatch.setattr(
        "app.services.billing.factory.get_settings",
        lambda: SimpleNamespace(billing_provider="paddle"),
    )
    provider = BillingProviderFactory.create()
    assert isinstance(provider, StripeProvider)


def test_webhook_factory_is_provider_specific():
    assert BillingProviderFactory.for_webhook("stripe").name == "stripe"
    assert BillingProviderFactory.for_webhook("razorpay").name == "razorpay"
    with pytest.raises(ValueError):
        BillingProviderFactory.for_webhook("unknown")


def test_set_customer_ids_dual_writes_stripe():
    org = SimpleNamespace(
        billing_provider=None,
        billing_customer_id=None,
        stripe_customer_id=None,
    )
    set_customer_ids(org, "stripe", "cus_123")
    assert org.billing_provider == "stripe"
    assert org.billing_customer_id == "cus_123"
    assert org.stripe_customer_id == "cus_123"


def test_set_customer_ids_razorpay_keeps_stripe_separate():
    org = SimpleNamespace(
        billing_provider="stripe",
        billing_customer_id="cus_old",
        stripe_customer_id="cus_old",
    )
    set_customer_ids(org, "razorpay", "cust_rzp_1")
    assert org.billing_provider == "razorpay"
    assert org.billing_customer_id == "cust_rzp_1"
    assert org.stripe_customer_id == "cus_old"


def test_razorpay_status_map_preserves_entitlements():
    """Active Razorpay subscription → paid entitlements unchanged."""
    org = SimpleNamespace(
        id=uuid4(),
        plan="starter",
        created_at=datetime.now(timezone.utc),
    )
    sub = SimpleNamespace(
        status="active",
        trial_ends_at=None,
        plan="starter",
        billing_interval="month",
        seat_count=1,
        current_period_end=None,
        cancel_at_period_end=False,
    )
    ents = resolve_entitlements(org, sub)
    assert ents.can_write is True
    assert ents.upgrade_simulator is True
    assert ents.ai_migration_assistant is False


def test_plan_ladder_entitlements_independent_of_provider():
    """Evaluation → Starter → Pro → Team entitlement ladder (provider-agnostic)."""
    cases = [
        ("free", False, False),
        ("starter", True, False),
        ("pro", True, False),
        ("team", True, True),
    ]
    for plan, simulator, migration in cases:
        org = SimpleNamespace(
            id=uuid4(),
            plan=plan,
            created_at=datetime.now(timezone.utc),
        )
        # Paid plans use active subscription; free uses expired evaluation
        if plan == "free":
            sub = SimpleNamespace(
                status="expired",
                trial_ends_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
                plan="free",
                billing_interval="month",
                seat_count=1,
                current_period_end=None,
                cancel_at_period_end=False,
            )
            ents = resolve_entitlements(org, sub)
            assert ents.upgrade_simulator is False
            continue
        sub = SimpleNamespace(
            status="active",
            trial_ends_at=None,
            plan=plan,
            billing_interval="month",
            seat_count=1,
            current_period_end=None,
            cancel_at_period_end=False,
        )
        ents = resolve_entitlements(org, sub)
        assert ents.upgrade_simulator is simulator
        assert ents.ai_migration_assistant is migration


def test_normalized_subscription_dataclass():
    snap = NormalizedSubscription(
        provider="razorpay",
        status="active",
        plan="pro",
        provider_subscription_id="sub_xyz",
    )
    assert snap.provider == "razorpay"
    assert snap.plan == "pro"


def test_razorpay_webhook_signature(monkeypatch):
    import hashlib
    import hmac
    import json

    secret = "whsec_test_secret"
    monkeypatch.setattr(
        "app.services.billing.razorpay_provider.settings",
        SimpleNamespace(
            razorpay_key_id="rzp_test",
            razorpay_key_secret="secret",
            razorpay_webhook_secret=secret,
            razorpay_plan_starter_monthly="",
            razorpay_plan_starter_yearly="",
            razorpay_plan_pro_monthly="",
            razorpay_plan_pro_yearly="",
            razorpay_plan_team_monthly="",
            razorpay_plan_team_yearly="",
        ),
    )
    provider = RazorpayProvider()
    body = json.dumps({"event": "subscription.activated", "payload": {}}).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    event = provider.verify_webhook(body, {"X-Razorpay-Signature": sig})
    assert event["event"] == "subscription.activated"
    with pytest.raises(ValueError):
        provider.verify_webhook(body, {"X-Razorpay-Signature": "bad"})


def test_subscription_provider_ids_dual_write_stripe_only():
    sub = SimpleNamespace(
        billing_provider=None,
        provider_subscription_id=None,
        provider_price_id=None,
        provider_payment_id=None,
        stripe_subscription_id=None,
        stripe_price_id=None,
    )
    set_subscription_provider_ids(
        sub,
        provider="stripe",
        subscription_id="sub_stripe",
        price_id="price_1",
    )
    assert sub.provider_subscription_id == "sub_stripe"
    assert sub.stripe_subscription_id == "sub_stripe"
    assert sub.stripe_price_id == "price_1"

    set_subscription_provider_ids(
        sub,
        provider="razorpay",
        subscription_id="sub_rzp",
        price_id="plan_1",
        payment_id="pay_1",
    )
    assert sub.billing_provider == "razorpay"
    assert sub.provider_subscription_id == "sub_rzp"
    assert sub.provider_payment_id == "pay_1"
    # Legacy Stripe ids preserved (not overwritten by Razorpay)
    assert sub.stripe_subscription_id == "sub_stripe"
