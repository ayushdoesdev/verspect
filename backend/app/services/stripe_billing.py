"""Compatibility shim for legacy imports.

Prefer:

    from app.services.billing import get_billing_provider

New code must not call Stripe APIs from this module.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.services.billing import get_billing_provider
from app.services.billing.stripe_provider import StripeProvider
from app.services.billing.sync import activate_plan_local  # noqa: F401 — re-export

__all__ = [
    "activate_plan_local",
    "create_checkout_session",
    "create_portal_session",
    "ensure_stripe_customer",
    "handle_stripe_webhook",
    "stripe_configured",
]


def stripe_configured() -> bool:
    return StripeProvider().is_configured()


async def ensure_stripe_customer(
    db: AsyncSession, org: Organization, email: Optional[str]
) -> str:
    return await StripeProvider().create_customer(db, org, email)


async def create_checkout_session(
    db: AsyncSession,
    *,
    org: Organization,
    plan: str,
    interval: str,
    success_url: str,
    cancel_url: str,
    customer_email: Optional[str],
) -> dict[str, Any]:
    provider = get_billing_provider()
    result = await provider.create_checkout_session(
        db,
        org=org,
        plan=plan,
        interval=interval,
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=customer_email,
    )
    return {
        "url": result.url,
        "session_id": result.session_id,
        "mode": result.mode,
        "provider": result.provider or provider.name,
    }


async def create_portal_session(
    db: AsyncSession,
    *,
    org: Organization,
    return_url: str,
) -> dict[str, Any]:
    provider = get_billing_provider()
    result = await provider.create_customer_portal(
        db, org=org, return_url=return_url
    )
    return {
        "url": result.url,
        "mode": result.mode,
        "provider": result.provider or provider.name,
    }


async def handle_stripe_webhook(
    db: AsyncSession, payload: bytes, sig_header: str
) -> dict[str, str]:
    provider = StripeProvider()
    return await provider.handle_webhook(
        db,
        payload,
        {"stripe-signature": sig_header, "Stripe-Signature": sig_header},
    )
