"""BillingProviderFactory — select gateway from BILLING_PROVIDER env.

Add a new provider by:
  1. Implementing BillingProvider
  2. Registering it in SUPPORTED_PROVIDERS / create()
Business services (entitlements, plans) never change.
"""

from __future__ import annotations

from typing import Optional

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.billing.base import BillingProvider
from app.services.billing.razorpay_provider import RazorpayProvider
from app.services.billing.stripe_provider import StripeProvider

logger = get_logger(__name__)

SUPPORTED_PROVIDERS = ("stripe", "razorpay")


class BillingProviderFactory:
    @classmethod
    def create(
        cls,
        name: Optional[str] = None,
        *,
        settings: Optional[Settings] = None,
    ) -> BillingProvider:
        settings = settings or get_settings()
        provider_name = (name or settings.billing_provider or "stripe").strip().lower()
        if provider_name not in SUPPORTED_PROVIDERS:
            logger.warning(
                "unsupported_billing_provider",
                requested=provider_name,
                fallback="stripe",
            )
            provider_name = "stripe"

        if provider_name == "razorpay":
            return RazorpayProvider()
        return StripeProvider()

    @classmethod
    def for_webhook(cls, provider: str) -> BillingProvider:
        """Resolve provider for a dedicated webhook endpoint (never cross-route)."""
        name = (provider or "").strip().lower()
        if name == "razorpay":
            return RazorpayProvider()
        if name == "stripe":
            return StripeProvider()
        raise ValueError(f"Unknown billing webhook provider: {provider}")


def get_billing_provider(name: Optional[str] = None) -> BillingProvider:
    return BillingProviderFactory.create(name)
