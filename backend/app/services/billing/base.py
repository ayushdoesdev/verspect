"""Provider-agnostic billing abstraction.

Application code talks only to BillingProvider. Concrete providers
(Stripe, Razorpay, Local) implement this interface.

Entitlements remain driven by Organization.plan + Subscription.status —
never by provider-specific fields.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization


class BillingNotConfigured(Exception):
    """Production checkout/portal requested without provider credentials."""


@dataclass
class CheckoutResult:
    url: str
    session_id: str
    mode: str  # stripe | razorpay | local | dev
    provider: str = ""


@dataclass
class PortalResult:
    url: str
    mode: str
    provider: str = ""


@dataclass
class NormalizedSubscription:
    """Provider-neutral subscription snapshot applied to our DB."""

    provider: str
    status: str
    plan: str
    interval: str = "month"
    provider_subscription_id: Optional[str] = None
    provider_price_id: Optional[str] = None
    provider_payment_id: Optional[str] = None
    provider_customer_id: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    canceled_at: Optional[datetime] = None
    seat_count: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedInvoice:
    """Provider-neutral invoice record (amounts in major currency units)."""

    provider: str
    provider_invoice_id: str
    status: str = "open"
    amount_due: float = 0.0
    amount_paid: float = 0.0
    currency: str = "usd"
    number: Optional[str] = None
    hosted_invoice_url: Optional[str] = None
    invoice_pdf: Optional[str] = None
    paid_at: Optional[datetime] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BillingProvider(ABC):
    """Abstract billing provider. Add new gateways by subclassing."""

    name: str = "base"

    @abstractmethod
    def is_configured(self) -> bool:
        """True when credentials are present and usable."""

    def publishable_key(self) -> Optional[str]:
        return None

    @abstractmethod
    async def create_customer(
        self,
        db: AsyncSession,
        org: Organization,
        email: Optional[str],
    ) -> str:
        """Create or return provider customer id; persist on org."""

    @abstractmethod
    async def create_checkout_session(
        self,
        db: AsyncSession,
        *,
        org: Organization,
        plan: str,
        interval: str,
        success_url: str,
        cancel_url: str,
        customer_email: Optional[str],
    ) -> CheckoutResult:
        """Start hosted checkout / subscription auth flow."""

    @abstractmethod
    async def create_customer_portal(
        self,
        db: AsyncSession,
        *,
        org: Organization,
        return_url: str,
    ) -> PortalResult:
        """Provider portal if supported; otherwise app billing page."""

    async def create_subscription(self, *args: Any, **kwargs: Any) -> Any:
        """Optional: create subscription directly (provider-specific)."""
        raise NotImplementedError(f"{self.name} does not support create_subscription")

    async def update_subscription(
        self,
        db: AsyncSession,
        *,
        org: Organization,
        plan: str,
        interval: str = "month",
        schedule_change_at: str = "now",
    ) -> Any:
        """Change plan. schedule_change_at: 'now' | 'period_end'."""
        raise NotImplementedError(f"{self.name} does not support update_subscription")

    async def cancel_subscription(
        self,
        db: AsyncSession,
        *,
        org: Organization,
        cancel_at_period_end: bool = True,
    ) -> Any:
        """Cancel subscription. Prefer cancel_at_period_end for SaaS lifecycle."""
        raise NotImplementedError(f"{self.name} does not support cancel_subscription")

    async def resume_subscription(
        self,
        db: AsyncSession,
        *,
        org: Organization,
    ) -> Any:
        """Undo pending cancellation (reactivate)."""
        raise NotImplementedError(f"{self.name} does not support resume_subscription")

    async def get_subscription(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(f"{self.name} does not support get_subscription")

    @abstractmethod
    def verify_webhook(self, payload: bytes, headers: Mapping[str, str]) -> Any:
        """Validate signature and return parsed event payload."""

    @abstractmethod
    async def handle_webhook(
        self,
        db: AsyncSession,
        payload: bytes,
        headers: Mapping[str, str],
    ) -> dict[str, str]:
        """Process provider webhook; sync subscription/invoice state."""

    def plan_from_price_ref(self, price_ref: Optional[str]) -> Optional[str]:
        """Map provider plan/price id → Verspect plan slug."""
        return None
