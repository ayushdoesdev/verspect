"""Stripe BillingProvider — preserves existing Checkout + Portal + webhook behavior."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.billing import Subscription
from app.models.organization import Organization
from app.services.billing.base import (
    BillingNotConfigured,
    BillingProvider,
    CheckoutResult,
    NormalizedInvoice,
    NormalizedSubscription,
    PortalResult,
)
from app.services.billing.sync import (
    activate_plan_local,
    apply_subscription_update,
    find_org_by_customer_id,
    record_normalized_invoice,
    set_customer_ids,
)

logger = get_logger(__name__)
settings = get_settings()

_PLACEHOLDER_KEYS = {
    "",
    "sk_test",
    "sk_test_",
    "sk_test_...",
    "sk_live_...",
    "changeme",
    "your_stripe_secret_key",
    "xxx",
}


class StripeProvider(BillingProvider):
    name = "stripe"

    def is_configured(self) -> bool:
        key = (settings.stripe_secret_key or "").strip()
        if not key or key.lower() in _PLACEHOLDER_KEYS:
            return False
        if key.endswith("...") or len(key) < 20:
            return False
        if not key.startswith(("sk_test_", "sk_live_", "rk_test_", "rk_live_")):
            return False
        return True

    def publishable_key(self) -> Optional[str]:
        return settings.stripe_publishable_key or None

    def _client(self):
        if not self.is_configured():
            return None
        import stripe

        stripe.api_key = settings.stripe_secret_key
        return stripe

    def _price_map(self) -> dict[tuple[str, str], str]:
        return {
            ("starter", "month"): (settings.stripe_price_starter_monthly or "").strip(),
            ("starter", "year"): (settings.stripe_price_starter_yearly or "").strip(),
            ("pro", "month"): (settings.stripe_price_pro_monthly or "").strip(),
            ("pro", "year"): (settings.stripe_price_pro_yearly or "").strip(),
            ("team", "month"): (settings.stripe_price_team_monthly or "").strip(),
            ("team", "year"): (settings.stripe_price_team_yearly or "").strip(),
        }

    def plan_from_price_ref(self, price_ref: Optional[str]) -> Optional[str]:
        if not price_ref:
            return None
        reverse = {pid: plan for (plan, _), pid in self._price_map().items() if pid}
        return reverse.get(price_ref)

    async def create_customer(
        self,
        db: AsyncSession,
        org: Organization,
        email: Optional[str],
    ) -> str:
        existing = org.billing_customer_id or org.stripe_customer_id
        if existing and (org.billing_provider or "stripe") == "stripe":
            set_customer_ids(org, self.name, existing)
            await db.flush()
            return existing

        stripe = self._client()
        if stripe is None:
            if settings.is_production:
                raise BillingNotConfigured(
                    "Stripe is not configured. Set STRIPE_SECRET_KEY."
                )
            customer_id = f"cus_dev_{org.id.hex[:16]}"
            set_customer_ids(org, self.name, customer_id)
            await db.flush()
            return customer_id

        customer = stripe.Customer.create(
            email=email,
            name=org.name,
            metadata={"organization_id": str(org.id), "slug": org.slug},
        )
        set_customer_ids(org, self.name, customer["id"])
        await db.flush()
        return customer["id"]

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
        from app.services.plans import CHECKOUT_PLANS, TRIAL_DAYS

        plan = plan.lower()
        interval = "year" if interval == "year" else "month"
        if plan not in CHECKOUT_PLANS:
            raise ValueError("Checkout only supported for starter, pro, and team plans")

        customer_id = await self.create_customer(db, org, customer_email)
        stripe = self._client()
        price_id = self._price_map().get((plan, interval), "")

        if stripe is None or not price_id:
            if settings.is_production:
                raise BillingNotConfigured(
                    "Stripe is not configured. Set STRIPE_SECRET_KEY and STRIPE_PRICE_*."
                )
            await activate_plan_local(
                db, org, plan=plan, interval=interval, trial_days=TRIAL_DAYS, provider="local"
            )
            return CheckoutResult(
                url=success_url,
                session_id=f"cs_dev_{org.id.hex[:12]}",
                mode="dev",
                provider=self.name,
            )

        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            subscription_data={
                "trial_period_days": TRIAL_DAYS,
                "metadata": {"organization_id": str(org.id), "plan": plan},
            },
            metadata={
                "organization_id": str(org.id),
                "plan": plan,
                "interval": interval,
                "billing_provider": self.name,
            },
            allow_promotion_codes=True,
        )
        return CheckoutResult(
            url=session.url,
            session_id=session.id,
            mode="stripe",
            provider=self.name,
        )

    async def create_customer_portal(
        self,
        db: AsyncSession,
        *,
        org: Organization,
        return_url: str,
    ) -> PortalResult:
        await self.create_customer(db, org, None)
        stripe = self._client()
        if stripe is None:
            if settings.is_production:
                raise BillingNotConfigured(
                    "Stripe is not configured. Set STRIPE_SECRET_KEY to use the billing portal."
                )
            return PortalResult(url=return_url, mode="dev", provider=self.name)
        customer_id = org.billing_customer_id or org.stripe_customer_id
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return PortalResult(url=session.url, mode="stripe", provider=self.name)

    async def get_subscription(self, subscription_id: str) -> Any:
        stripe = self._client()
        if stripe is None:
            raise RuntimeError("Stripe not configured")
        return stripe.Subscription.retrieve(subscription_id)

    async def update_subscription(
        self,
        db: AsyncSession,
        *,
        org: Organization,
        plan: str,
        interval: str = "month",
        schedule_change_at: str = "now",
    ) -> Any:
        """Swap price on the org's Stripe subscription.

        schedule_change_at='now' → immediate change with proration (upgrades).
        schedule_change_at='period_end' → store intent in Stripe metadata only;
        lifecycle service keeps current entitlements until period end, then applies.
        """
        from app.services.plans import CHECKOUT_PLANS

        plan = plan.lower()
        interval = "year" if interval == "year" else "month"
        if plan not in CHECKOUT_PLANS:
            raise ValueError("Plan change only supported for starter, pro, and team")
        stripe = self._client()
        if stripe is None:
            raise RuntimeError("Stripe not configured")
        price_id = self._price_map().get((plan, interval), "")
        if not price_id:
            raise ValueError(f"No Stripe price id configured for {plan}/{interval}")

        sub = (
            await db.execute(
                select(Subscription).where(Subscription.organization_id == org.id)
            )
        ).scalar_one_or_none()
        sid = (sub.provider_subscription_id or sub.stripe_subscription_id) if sub else None
        if not sid:
            raise ValueError("No Stripe subscription on organization")

        current = stripe.Subscription.retrieve(sid)
        when = (schedule_change_at or "now").lower()

        if when in {"period_end", "cycle_end"}:
            # Do not change the billed price yet — annotate for period-end apply.
            updated = stripe.Subscription.modify(
                sid,
                metadata={
                    **dict(current.get("metadata") or {}),
                    "organization_id": str(org.id),
                    "pending_plan": plan,
                    "pending_interval": interval,
                    "pending_price_id": price_id,
                },
                cancel_at_period_end=False,
            )
            # Do not apply_subscription_update with the target plan — lifecycle owns pending.
            return updated

        item_id = current["items"]["data"][0]["id"]
        updated = stripe.Subscription.modify(
            sid,
            items=[{"id": item_id, "price": price_id}],
            proration_behavior="create_prorations",
            metadata={
                **dict(current.get("metadata") or {}),
                "organization_id": str(org.id),
                "plan": plan,
                "pending_plan": "",
            },
            cancel_at_period_end=False,
        )
        snapshot = self._normalize_subscription(updated, plan_hint=plan)
        await apply_subscription_update(db, organization_id=org.id, snapshot=snapshot)
        return updated

    async def cancel_subscription(
        self,
        db: AsyncSession,
        *,
        org: Organization,
        cancel_at_period_end: bool = True,
    ) -> Any:
        stripe = self._client()
        if stripe is None:
            raise RuntimeError("Stripe not configured")
        sub = (
            await db.execute(
                select(Subscription).where(Subscription.organization_id == org.id)
            )
        ).scalar_one_or_none()
        sid = (sub.provider_subscription_id or sub.stripe_subscription_id) if sub else None
        if not sid:
            raise ValueError("No Stripe subscription on organization")
        if cancel_at_period_end:
            updated = stripe.Subscription.modify(sid, cancel_at_period_end=True)
        else:
            updated = stripe.Subscription.cancel(sid)
        snapshot = self._normalize_subscription(updated, plan_hint=org.plan)
        # Keep paid plan while cancel_at_period_end — apply_subscription_update
        # only drops to free on terminal canceled status.
        await apply_subscription_update(db, organization_id=org.id, snapshot=snapshot)
        return updated

    async def resume_subscription(
        self,
        db: AsyncSession,
        *,
        org: Organization,
    ) -> Any:
        stripe = self._client()
        if stripe is None:
            raise RuntimeError("Stripe not configured")
        sub = (
            await db.execute(
                select(Subscription).where(Subscription.organization_id == org.id)
            )
        ).scalar_one_or_none()
        sid = (sub.provider_subscription_id or sub.stripe_subscription_id) if sub else None
        if not sid:
            raise ValueError("No Stripe subscription on organization")
        updated = stripe.Subscription.modify(sid, cancel_at_period_end=False)
        snapshot = self._normalize_subscription(updated, plan_hint=org.plan)
        await apply_subscription_update(db, organization_id=org.id, snapshot=snapshot)
        return updated

    def verify_webhook(self, payload: bytes, headers: Mapping[str, str]) -> Any:
        stripe = self._client()
        if stripe is None:
            raise ValueError("Stripe not configured")
        sig = headers.get("stripe-signature") or headers.get("Stripe-Signature") or ""
        return stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )

    def _ts(self, value: Any) -> Optional[datetime]:
        if not value:
            return None
        return datetime.fromtimestamp(int(value), tz=timezone.utc)

    def _normalize_subscription(
        self,
        stripe_sub: dict[str, Any],
        *,
        plan_hint: Optional[str] = None,
        org_plan: Optional[str] = None,
    ) -> NormalizedSubscription:
        items = ((stripe_sub.get("items") or {}).get("data") or [])
        price_id = None
        if items:
            price_id = ((items[0].get("price") or {}).get("id"))
        plan = (
            plan_hint
            or (stripe_sub.get("metadata") or {}).get("plan")
            or self.plan_from_price_ref(price_id)
            or org_plan
            or "pro"
        )
        return NormalizedSubscription(
            provider=self.name,
            status=stripe_sub.get("status") or "active",
            plan=str(plan).lower(),
            interval="year"
            if ((items[0].get("price") or {}).get("recurring") or {}).get("interval") == "year"
            else "month"
            if items
            else "month",
            provider_subscription_id=stripe_sub.get("id"),
            provider_price_id=price_id,
            provider_customer_id=stripe_sub.get("customer"),
            trial_ends_at=self._ts(stripe_sub.get("trial_end")),
            current_period_start=self._ts(stripe_sub.get("current_period_start")),
            current_period_end=self._ts(stripe_sub.get("current_period_end")),
            cancel_at_period_end=bool(stripe_sub.get("cancel_at_period_end")),
            canceled_at=self._ts(stripe_sub.get("canceled_at")),
            metadata={"source": "stripe"},
        )

    async def handle_webhook(
        self,
        db: AsyncSession,
        payload: bytes,
        headers: Mapping[str, str],
    ) -> dict[str, str]:
        stripe = self._client()
        if stripe is None:
            return {"status": "ignored", "reason": "stripe_not_configured"}

        try:
            event = self.verify_webhook(payload, headers)
        except Exception as exc:  # noqa: BLE001
            logger.warning("stripe_webhook_invalid", error=str(exc))
            raise ValueError("Invalid Stripe signature") from exc

        etype = event["type"]
        data = event["data"]["object"]
        logger.info("stripe_webhook", type=etype)

        if etype == "checkout.session.completed":
            org_id = (data.get("metadata") or {}).get("organization_id")
            plan = (data.get("metadata") or {}).get("plan")
            sub_id = data.get("subscription")
            if org_id and sub_id:
                sub_obj = stripe.Subscription.retrieve(sub_id)
                org = (
                    await db.execute(
                        select(Organization).where(Organization.id == UUID(org_id))
                    )
                ).scalar_one_or_none()
                snapshot = self._normalize_subscription(
                    sub_obj, plan_hint=plan, org_plan=org.plan if org else None
                )
                await apply_subscription_update(
                    db, organization_id=UUID(org_id), snapshot=snapshot
                )
        elif etype in {
            "customer.subscription.updated",
            "customer.subscription.created",
            "customer.subscription.deleted",
        }:
            org_id = (data.get("metadata") or {}).get("organization_id")
            if not org_id:
                cust = data.get("customer")
                org = await find_org_by_customer_id(
                    db, provider=self.name, customer_id=cust or ""
                )
                if org:
                    org_id = str(org.id)
            if org_id:
                org = (
                    await db.execute(
                        select(Organization).where(Organization.id == UUID(org_id))
                    )
                ).scalar_one_or_none()
                snapshot = self._normalize_subscription(
                    data, org_plan=org.plan if org else None
                )
                await apply_subscription_update(
                    db, organization_id=UUID(org_id), snapshot=snapshot
                )
        elif etype in {"invoice.paid", "invoice.payment_failed", "invoice.finalized"}:
            cust = data.get("customer")
            org = await find_org_by_customer_id(
                db, provider=self.name, customer_id=cust or ""
            )
            if org:
                paid_at = None
                if data.get("status_transitions", {}).get("paid_at"):
                    paid_at = self._ts(data["status_transitions"]["paid_at"])
                await record_normalized_invoice(
                    db,
                    org.id,
                    NormalizedInvoice(
                        provider=self.name,
                        provider_invoice_id=data.get("id") or "",
                        status=data.get("status") or "open",
                        amount_due=(data.get("amount_due") or 0) / 100.0,
                        amount_paid=(data.get("amount_paid") or 0) / 100.0,
                        currency=data.get("currency") or "usd",
                        number=data.get("number"),
                        hosted_invoice_url=data.get("hosted_invoice_url"),
                        invoice_pdf=data.get("invoice_pdf"),
                        paid_at=paid_at,
                    ),
                )
                if etype == "invoice.payment_failed":
                    sub = (
                        await db.execute(
                            select(Subscription).where(
                                Subscription.organization_id == org.id
                            )
                        )
                    ).scalar_one_or_none()
                    if sub:
                        sub.status = "past_due"
                        await db.flush()

        await db.commit()
        return {"status": "ok", "type": etype, "provider": self.name}
