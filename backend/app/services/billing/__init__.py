"""Multi-provider billing — Stripe, Razorpay, extensible.

Application code should use:

    from app.services.billing import get_billing_provider
    provider = get_billing_provider()
    await provider.create_checkout_session(...)

Never import Stripe/Razorpay SDKs outside provider modules.
"""

from app.services.billing.base import (
    BillingNotConfigured,
    BillingProvider,
    CheckoutResult,
    NormalizedInvoice,
    NormalizedSubscription,
    PortalResult,
)
from app.services.billing.factory import (
    BillingProviderFactory,
    SUPPORTED_PROVIDERS,
    get_billing_provider,
)
from app.services.billing.sync import activate_plan_local, apply_subscription_update
from app.services.billing.lifecycle import (
    cancel_subscription,
    change_plan,
    reactivate_subscription,
)

__all__ = [
    "BillingNotConfigured",
    "BillingProvider",
    "BillingProviderFactory",
    "CheckoutResult",
    "NormalizedInvoice",
    "NormalizedSubscription",
    "PortalResult",
    "SUPPORTED_PROVIDERS",
    "activate_plan_local",
    "apply_subscription_update",
    "cancel_subscription",
    "change_plan",
    "get_billing_provider",
    "reactivate_subscription",
]
