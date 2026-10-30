"""Provider-neutral subscription / invoice persistence.

Business rules for plan activation live here — not in Stripe/Razorpay adapters.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Invoice, Subscription
from app.models.organization import Organization
from app.services.billing.base import NormalizedInvoice, NormalizedSubscription


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def set_customer_ids(org: Organization, provider: str, customer_id: str) -> None:
    """Dual-write canonical + legacy Stripe customer columns."""
    org.billing_provider = provider
    org.billing_customer_id = customer_id
    if provider == "stripe":
        org.stripe_customer_id = customer_id


def set_subscription_provider_ids(
    sub: Subscription,
    *,
    provider: str,
    subscription_id: Optional[str] = None,
    price_id: Optional[str] = None,
    payment_id: Optional[str] = None,
) -> None:
    sub.billing_provider = provider
    if subscription_id is not None:
        sub.provider_subscription_id = subscription_id
        if provider == "stripe":
            sub.stripe_subscription_id = subscription_id
    if price_id is not None:
        sub.provider_price_id = price_id
        if provider == "stripe":
            sub.stripe_price_id = price_id
    if payment_id is not None:
        sub.provider_payment_id = payment_id


async def activate_plan_local(
    db: AsyncSession,
    org: Organization,
    *,
    plan: str,
    interval: str = "month",
    trial_days: int = 0,
    provider: str = "local",
) -> Subscription:
    """Dev / offline checkout — activates plan without a payment gateway."""
    result = await db.execute(
        select(Subscription).where(Subscription.organization_id == org.id)
    )
    sub = result.scalar_one_or_none()
    now = _utcnow()
    trial_end = now + timedelta(days=trial_days) if trial_days else None
    if sub is None:
        sub = Subscription(organization_id=org.id)
        db.add(sub)
    sub.plan = plan
    sub.status = "trialing" if trial_days else "active"
    sub.billing_interval = interval
    sub.trial_ends_at = trial_end
    sub.current_period_start = now
    sub.current_period_end = now + timedelta(days=365 if interval == "year" else 30)
    sub.cancel_at_period_end = False
    sub.pending_plan = None
    sub.pending_interval = None
    sub.pending_change_type = None
    sub.pending_change_effective_at = None
    sub.billing_provider = provider
    org.plan = plan
    if not org.billing_provider:
        org.billing_provider = provider
    await db.flush()
    return sub


async def apply_subscription_update(
    db: AsyncSession,
    *,
    organization_id: UUID,
    snapshot: NormalizedSubscription,
) -> None:
    """Upsert subscription + org.plan from a normalized provider snapshot."""
    from app.services.billing.soft_limits import enforce_plan_soft_limits
    from app.services.plans import PAID_PLANS

    org = (
        await db.execute(select(Organization).where(Organization.id == organization_id))
    ).scalar_one_or_none()
    if org is None:
        return

    sub = (
        await db.execute(
            select(Subscription).where(Subscription.organization_id == org.id)
        )
    ).scalar_one_or_none()
    if sub is None:
        sub = Subscription(organization_id=org.id)
        db.add(sub)

    previous_plan = (org.plan or "free").lower()
    status = (snapshot.status or "active").lower()
    plan = (snapshot.plan or org.plan or "free").lower()

    set_subscription_provider_ids(
        sub,
        provider=snapshot.provider,
        subscription_id=snapshot.provider_subscription_id,
        price_id=snapshot.provider_price_id,
        payment_id=snapshot.provider_payment_id,
    )
    if snapshot.provider_customer_id:
        set_customer_ids(org, snapshot.provider, snapshot.provider_customer_id)

    sub.status = status
    sub.billing_interval = snapshot.interval or sub.billing_interval or "month"
    sub.seat_count = snapshot.seat_count or sub.seat_count or 1
    sub.trial_ends_at = snapshot.trial_ends_at
    sub.current_period_start = snapshot.current_period_start
    sub.current_period_end = snapshot.current_period_end
    sub.cancel_at_period_end = bool(snapshot.cancel_at_period_end)
    if snapshot.canceled_at:
        sub.canceled_at = snapshot.canceled_at

    # While cancel_at_period_end is set, keep paid entitlements until terminal cancel.
    if (
        snapshot.cancel_at_period_end
        and status in {"active", "trialing", "authenticated", "past_due"}
        and previous_plan in PAID_PLANS
    ):
        sub.plan = previous_plan
        org.plan = previous_plan
        if not sub.pending_plan:
            sub.pending_plan = "free"
            sub.pending_change_type = "cancel"
            sub.pending_change_effective_at = snapshot.current_period_end
    elif status in {"canceled", "cancelled", "unpaid", "incomplete_expired", "expired"}:
        sub.plan = "free"
        org.plan = "free"
        sub.pending_plan = None
        sub.pending_interval = None
        sub.pending_change_type = None
        sub.pending_change_effective_at = None
        sub.cancel_at_period_end = False
    elif status in {"active", "trialing", "authenticated", "paused", "past_due", "halted"}:
        # Razorpay uses authenticated/halted; map paused to past_due-like access
        if status in {"paused", "halted"}:
            sub.status = "past_due"
        # If we have a scheduled downgrade to a different plan, don't apply early
        if (
            sub.pending_plan
            and sub.pending_change_type == "downgrade"
            and plan == (sub.pending_plan or "").lower()
            and previous_plan != plan
            and sub.pending_change_effective_at
            and sub.pending_change_effective_at > _utcnow()
        ):
            sub.plan = previous_plan
            org.plan = previous_plan
        else:
            sub.plan = plan
            org.plan = plan
            if sub.pending_plan and plan == (sub.pending_plan or "").lower():
                sub.pending_plan = None
                sub.pending_interval = None
                sub.pending_change_type = None
                sub.pending_change_effective_at = None
    else:
        sub.plan = plan if status in {"active", "trialing"} else org.plan
        if status in {"active", "trialing"}:
            org.plan = plan

    if snapshot.metadata:
        meta = dict(sub.extra_metadata or {})
        meta.update(snapshot.metadata)
        sub.extra_metadata = meta

    await db.flush()

    # Soft-enforce when plan actually shrank (never delete data)
    new_plan = (org.plan or "free").lower()
    rank = {"free": 0, "starter": 1, "pro": 2, "team": 3, "enterprise": 4}
    if rank.get(new_plan, 0) < rank.get(previous_plan, 0):
        await enforce_plan_soft_limits(db, org)


async def record_normalized_invoice(
    db: AsyncSession,
    org_id: UUID,
    invoice: NormalizedInvoice,
) -> None:
    """Idempotent invoice upsert using provider + provider_invoice_id."""
    existing = None
    if invoice.provider == "stripe" and invoice.provider_invoice_id:
        existing = (
            await db.execute(
                select(Invoice).where(
                    Invoice.stripe_invoice_id == invoice.provider_invoice_id
                )
            )
        ).scalar_one_or_none()
    if existing is None and invoice.provider_invoice_id:
        existing = (
            await db.execute(
                select(Invoice).where(
                    Invoice.billing_provider == invoice.provider,
                    Invoice.provider_invoice_id == invoice.provider_invoice_id,
                )
            )
        ).scalar_one_or_none()

    inv = existing or Invoice(organization_id=org_id)
    if existing is None:
        db.add(inv)

    inv.billing_provider = invoice.provider
    inv.provider_invoice_id = invoice.provider_invoice_id
    if invoice.provider == "stripe":
        inv.stripe_invoice_id = invoice.provider_invoice_id
    inv.number = invoice.number
    inv.status = invoice.status or "open"
    inv.amount_due = invoice.amount_due
    inv.amount_paid = invoice.amount_paid
    inv.currency = invoice.currency or "usd"
    inv.hosted_invoice_url = invoice.hosted_invoice_url
    inv.invoice_pdf = invoice.invoice_pdf
    inv.paid_at = invoice.paid_at
    inv.period_start = invoice.period_start
    inv.period_end = invoice.period_end
    if invoice.metadata:
        inv.provider_metadata = dict(invoice.metadata)
    await db.flush()


async def find_org_by_customer_id(
    db: AsyncSession,
    *,
    provider: str,
    customer_id: str,
) -> Optional[Organization]:
    if not customer_id:
        return None
    org = (
        await db.execute(
            select(Organization).where(
                Organization.billing_provider == provider,
                Organization.billing_customer_id == customer_id,
            )
        )
    ).scalar_one_or_none()
    if org:
        return org
    # Legacy Stripe column fallback
    if provider == "stripe":
        return (
            await db.execute(
                select(Organization).where(Organization.stripe_customer_id == customer_id)
            )
        ).scalar_one_or_none()
    return None
