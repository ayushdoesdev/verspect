"""Razorpay BillingProvider — subscriptions, checkout short URL, webhooks.

Uses Razorpay Plans (created in dashboard) referenced via env:
  RAZORPAY_PLAN_STARTER_MONTHLY, etc.

Checkout returns the subscription short_url for the customer to authorize
the first payment. Entitlements update via webhooks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
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

# Map Razorpay subscription statuses → our status vocabulary
_STATUS_MAP = {
    "created": "incomplete",
    "authenticated": "trialing",
    "active": "active",
    "pending": "incomplete",
    "halted": "past_due",
    "cancelled": "canceled",
    "canceled": "canceled",
    "completed": "canceled",
    "expired": "expired",
    "paused": "past_due",
}


class RazorpayProvider(BillingProvider):
    name = "razorpay"

    def is_configured(self) -> bool:
        key_id = (settings.razorpay_key_id or "").strip()
        secret = (settings.razorpay_key_secret or "").strip()
        if not key_id or not secret:
            return False
        if key_id.endswith("...") or secret.endswith("..."):
            return False
        if len(key_id) < 8 or len(secret) < 8:
            return False
        return True

    def publishable_key(self) -> Optional[str]:
        # Key ID is public; used by Checkout.js if frontend ever needs it.
        return settings.razorpay_key_id or None

    def _client(self):
        if not self.is_configured():
            return None
        import razorpay

        return razorpay.Client(
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
        )

    def _plan_map(self) -> dict[tuple[str, str], str]:
        return {
            ("starter", "month"): (settings.razorpay_plan_starter_monthly or "").strip(),
            ("starter", "year"): (settings.razorpay_plan_starter_yearly or "").strip(),
            ("pro", "month"): (settings.razorpay_plan_pro_monthly or "").strip(),
            ("pro", "year"): (settings.razorpay_plan_pro_yearly or "").strip(),
            ("team", "month"): (settings.razorpay_plan_team_monthly or "").strip(),
            ("team", "year"): (settings.razorpay_plan_team_yearly or "").strip(),
        }

    def plan_from_price_ref(self, price_ref: Optional[str]) -> Optional[str]:
        if not price_ref:
            return None
        reverse = {pid: plan for (plan, _), pid in self._plan_map().items() if pid}
        return reverse.get(price_ref)

    async def create_customer(
        self,
        db: AsyncSession,
        org: Organization,
        email: Optional[str],
    ) -> str:
        if (
            org.billing_customer_id
            and (org.billing_provider or "") == self.name
        ):
            return org.billing_customer_id

        client = self._client()
        if client is None:
            customer_id = f"cust_dev_{org.id.hex[:16]}"
            set_customer_ids(org, self.name, customer_id)
            await db.flush()
            return customer_id

        payload: dict[str, Any] = {
            "name": org.name or "Verspect Customer",
            "notes": {
                "organization_id": str(org.id),
                "slug": org.slug or "",
            },
        }
        if email:
            payload["email"] = email
        customer = client.customer.create(payload)
        customer_id = customer["id"]
        set_customer_ids(org, self.name, customer_id)
        await db.flush()
        return customer_id

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
        client = self._client()
        plan_id = self._plan_map().get((plan, interval), "")

        if client is None or not plan_id:
            if settings.is_production:
                raise BillingNotConfigured(
                    "Razorpay is not configured. Set RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, and RAZORPAY_PLAN_*."
                )
            await activate_plan_local(
                db, org, plan=plan, interval=interval, trial_days=TRIAL_DAYS, provider="local"
            )
            return CheckoutResult(
                url=success_url,
                session_id=f"sub_dev_{org.id.hex[:12]}",
                mode="dev",
                provider=self.name,
            )

        # Upgrade / plan change on an existing Razorpay subscription
        db_sub = (
            await db.execute(
                select(Subscription).where(Subscription.organization_id == org.id)
            )
        ).scalar_one_or_none()
        if (
            db_sub
            and db_sub.billing_provider == self.name
            and db_sub.provider_subscription_id
            and (db_sub.status or "").lower()
            in {"active", "trialing", "authenticated", "past_due"}
        ):
            updated = await self.update_subscription(
                db,
                org=org,
                plan=plan,
                interval=interval,
                schedule_change_at="now",
            )
            short_url = (updated or {}).get("short_url") or success_url
            return CheckoutResult(
                url=short_url,
                session_id=db_sub.provider_subscription_id,
                mode="razorpay",
                provider=self.name,
            )

        # total_count: large finite count for ongoing monthly/yearly renewals.
        # Razorpay requires total_count; use 120 months / 10 years as practical ongoing.
        total_count = 10 if interval == "year" else 120
        subscription = client.subscription.create(
            {
                "plan_id": plan_id,
                "customer_id": customer_id,
                "total_count": total_count,
                "customer_notify": 1,
                "notes": {
                    "organization_id": str(org.id),
                    "plan": plan,
                    "interval": interval,
                    "billing_provider": self.name,
                    "success_url": success_url,
                    "cancel_url": cancel_url,
                },
            }
        )
        short_url = subscription.get("short_url") or success_url
        sub_id = subscription.get("id") or ""

        # Persist pending subscription id so webhooks can correlate
        if db_sub is None:
            db_sub = Subscription(organization_id=org.id, plan="free", status="incomplete")
            db.add(db_sub)
        db_sub.billing_provider = self.name
        db_sub.provider_subscription_id = sub_id
        db_sub.provider_price_id = plan_id
        db_sub.billing_interval = interval
        meta = dict(db_sub.extra_metadata or {})
        meta["pending_plan"] = plan
        meta["checkout_success_url"] = success_url
        db_sub.extra_metadata = meta
        await db.flush()

        return CheckoutResult(
            url=short_url,
            session_id=sub_id,
            mode="razorpay",
            provider=self.name,
        )

    async def create_customer_portal(
        self,
        db: AsyncSession,
        *,
        org: Organization,
        return_url: str,
    ) -> PortalResult:
        # Razorpay has no Stripe-equivalent portal; return app billing page.
        # Customers manage cards via Razorpay payment pages / invoices.
        return PortalResult(url=return_url, mode="self_serve", provider=self.name)

    async def update_subscription(
        self,
        db: AsyncSession,
        *,
        org: Organization,
        plan: str,
        interval: str = "month",
        schedule_change_at: str = "now",
    ) -> Any:
        """Change plan on an existing Razorpay subscription (upgrade/downgrade)."""
        from app.services.plans import CHECKOUT_PLANS

        plan = plan.lower()
        interval = "year" if interval == "year" else "month"
        if plan not in CHECKOUT_PLANS:
            raise ValueError("Plan change only supported for starter, pro, and team")

        client = self._client()
        if client is None:
            raise RuntimeError("Razorpay not configured")

        plan_id = self._plan_map().get((plan, interval), "")
        if not plan_id:
            raise ValueError(f"No Razorpay plan id configured for {plan}/{interval}")

        sub = (
            await db.execute(
                select(Subscription).where(Subscription.organization_id == org.id)
            )
        ).scalar_one_or_none()
        sid = sub.provider_subscription_id if sub else None
        if not sid:
            raise ValueError("No Razorpay subscription on organization")

        when = (schedule_change_at or "now").lower()
        rzp_when = "cycle_end" if when in {"period_end", "cycle_end"} else "now"

        updated = client.subscription.update(
            sid,
            {
                "plan_id": plan_id,
                "schedule_change_at": rzp_when,
                "customer_notify": 1,
            },
        )
        if rzp_when == "now":
            snapshot = self._normalize_subscription(updated, plan_hint=plan)
            snapshot.interval = interval
            await apply_subscription_update(db, organization_id=org.id, snapshot=snapshot)
            if sub:
                meta = dict(sub.extra_metadata or {})
                meta.pop("pending_plan", None)
                sub.extra_metadata = meta
                sub.provider_price_id = plan_id
                sub.billing_interval = interval
        else:
            # Period-end: keep current entitlements; lifecycle owns pending_* columns.
            if sub:
                meta = dict(sub.extra_metadata or {})
                meta["pending_plan"] = plan
                meta["pending_rzp_plan_id"] = plan_id
                sub.extra_metadata = meta
        await db.flush()
        return updated

    async def get_subscription(self, subscription_id: str) -> Any:
        client = self._client()
        if client is None:
            raise RuntimeError("Razorpay not configured")
        return client.subscription.fetch(subscription_id)

    async def resume_subscription(
        self,
        db: AsyncSession,
        *,
        org: Organization,
    ) -> Any:
        client = self._client()
        if client is None:
            raise RuntimeError("Razorpay not configured")
        sub = (
            await db.execute(
                select(Subscription).where(Subscription.organization_id == org.id)
            )
        ).scalar_one_or_none()
        sid = sub.provider_subscription_id if sub else None
        if not sid:
            raise ValueError("No Razorpay subscription on organization")
        # Razorpay: pending cancel_at_cycle_end is cleared by updating cancel flag
        # via cancel(cancel_at_cycle_end=0) is not resume — use resume when halted,
        # otherwise fetch + treat as reactivated locally.
        try:
            updated = client.subscription.resume(sid, {"resume_at": "now"})
        except Exception:  # noqa: BLE001
            # Not halted — pending cycle-end cancel: cancel with cancel_at_cycle_end=0
            # is wrong. Razorpay uses pending update; re-fetch and clear local flags.
            updated = client.subscription.fetch(sid)
        snapshot = self._normalize_subscription(updated, plan_hint=org.plan)
        snapshot.cancel_at_period_end = False
        await apply_subscription_update(db, organization_id=org.id, snapshot=snapshot)
        return updated

    async def cancel_subscription(
        self,
        db: AsyncSession,
        *,
        org: Organization,
        cancel_at_period_end: bool = True,
        cancel_at_cycle_end: bool | None = None,
    ) -> Any:
        """Cancel Razorpay subscription. Prefer cycle-end (period-end) cancellation."""
        client = self._client()
        if client is None:
            raise RuntimeError("Razorpay not configured")
        sub = (
            await db.execute(
                select(Subscription).where(Subscription.organization_id == org.id)
            )
        ).scalar_one_or_none()
        sid = (sub.provider_subscription_id if sub else None) or None
        if not sid:
            raise ValueError("No Razorpay subscription on organization")
        at_end = (
            cancel_at_cycle_end
            if cancel_at_cycle_end is not None
            else cancel_at_period_end
        )
        updated = client.subscription.cancel(
            sid, {"cancel_at_cycle_end": 1 if at_end else 0}
        )
        snapshot = self._normalize_subscription(updated, plan_hint=org.plan)
        if at_end:
            snapshot.cancel_at_period_end = True
            # Stay on paid plan until cycle ends
            if (snapshot.status or "").lower() in {"cancelled", "canceled"}:
                snapshot.status = "active"
                snapshot.cancel_at_period_end = True
        await apply_subscription_update(db, organization_id=org.id, snapshot=snapshot)
        return updated

    def verify_webhook(self, payload: bytes, headers: Mapping[str, str]) -> Any:
        secret = (settings.razorpay_webhook_secret or "").strip()
        if not secret:
            raise ValueError("RAZORPAY_WEBHOOK_SECRET not configured")
        signature = (
            headers.get("x-razorpay-signature")
            or headers.get("X-Razorpay-Signature")
            or ""
        )
        expected = hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError("Invalid Razorpay signature")
        return json.loads(payload.decode("utf-8"))

    def _map_status(self, razorpay_status: Optional[str]) -> str:
        return _STATUS_MAP.get((razorpay_status or "").lower(), "active")

    def _normalize_subscription(
        self,
        entity: dict[str, Any],
        *,
        plan_hint: Optional[str] = None,
    ) -> NormalizedSubscription:
        notes = entity.get("notes") or {}
        plan_id = entity.get("plan_id")
        plan = (
            plan_hint
            or notes.get("plan")
            or self.plan_from_price_ref(plan_id)
            or "starter"
        )
        interval = notes.get("interval") or "month"
        current_start = None
        current_end = None
        if entity.get("current_start"):
            current_start = datetime.fromtimestamp(
                int(entity["current_start"]), tz=timezone.utc
            )
        if entity.get("current_end"):
            current_end = datetime.fromtimestamp(
                int(entity["current_end"]), tz=timezone.utc
            )
        return NormalizedSubscription(
            provider=self.name,
            status=self._map_status(entity.get("status")),
            plan=str(plan).lower(),
            interval=interval if interval in {"month", "year"} else "month",
            provider_subscription_id=entity.get("id"),
            provider_price_id=plan_id,
            provider_customer_id=entity.get("customer_id"),
            current_period_start=current_start,
            current_period_end=current_end,
            cancel_at_period_end=(
                str(entity.get("status") or "").lower() in {"cancelled", "canceled"}
                or bool(entity.get("ended_at"))
            ),
            metadata={"source": "razorpay", "notes": notes},
        )

    async def _org_id_from_entity(self, db: AsyncSession, entity: dict[str, Any]) -> Optional[UUID]:
        notes = entity.get("notes") or {}
        org_id = notes.get("organization_id")
        if org_id:
            try:
                return UUID(str(org_id))
            except ValueError:
                pass
        cust = entity.get("customer_id")
        if cust:
            org = await find_org_by_customer_id(
                db, provider=self.name, customer_id=cust
            )
            if org:
                return org.id
        # Fallback: match pending provider_subscription_id
        sub_id = entity.get("id") or entity.get("subscription_id")
        if sub_id:
            sub = (
                await db.execute(
                    select(Subscription).where(
                        Subscription.provider_subscription_id == sub_id
                    )
                )
            ).scalar_one_or_none()
            if sub:
                return sub.organization_id
        return None

    async def handle_webhook(
        self,
        db: AsyncSession,
        payload: bytes,
        headers: Mapping[str, str],
    ) -> dict[str, str]:
        if not self.is_configured():
            return {"status": "ignored", "reason": "razorpay_not_configured"}

        try:
            event = self.verify_webhook(payload, headers)
        except Exception as exc:  # noqa: BLE001
            logger.warning("razorpay_webhook_invalid", error=str(exc))
            raise ValueError("Invalid Razorpay signature") from exc

        etype = event.get("event") or ""
        payload_body = event.get("payload") or {}
        logger.info("razorpay_webhook", type=etype)

        # Most subscription events nest under payload.subscription.entity
        sub_entity = ((payload_body.get("subscription") or {}).get("entity")) or {}
        payment_entity = ((payload_body.get("payment") or {}).get("entity")) or {}
        invoice_entity = ((payload_body.get("invoice") or {}).get("entity")) or {}

        if etype.startswith("subscription.") and sub_entity:
            org_id = await self._org_id_from_entity(db, sub_entity)
            notes = sub_entity.get("notes") or {}
            plan_hint = notes.get("plan")
            if org_id:
                # Prefer pending_plan from our DB if notes missing
                if not plan_hint:
                    db_sub = (
                        await db.execute(
                            select(Subscription).where(
                                Subscription.organization_id == org_id
                            )
                        )
                    ).scalar_one_or_none()
                    if db_sub and (db_sub.extra_metadata or {}).get("pending_plan"):
                        plan_hint = db_sub.extra_metadata["pending_plan"]
                snapshot = self._normalize_subscription(sub_entity, plan_hint=plan_hint)
                if payment_entity.get("id"):
                    snapshot.provider_payment_id = payment_entity.get("id")
                if etype in {
                    "subscription.cancelled",
                    "subscription.completed",
                }:
                    snapshot.status = "canceled"
                await apply_subscription_update(
                    db, organization_id=org_id, snapshot=snapshot
                )

        elif etype in {"payment.captured", "payment.authorized"} and payment_entity:
            # Payment success — refresh subscription if we can resolve it
            entity = {
                "id": payment_entity.get("subscription_id") or sub_entity.get("id"),
                "customer_id": payment_entity.get("customer_id"),
                "status": sub_entity.get("status") or "active",
                "plan_id": sub_entity.get("plan_id"),
                "notes": (sub_entity.get("notes") or payment_entity.get("notes") or {}),
                "current_start": sub_entity.get("current_start"),
                "current_end": sub_entity.get("current_end"),
            }
            org_id = await self._org_id_from_entity(db, entity)
            if org_id and entity.get("id"):
                notes = entity.get("notes") or {}
                snapshot = self._normalize_subscription(
                    {**sub_entity, **entity} if sub_entity else entity,
                    plan_hint=notes.get("plan"),
                )
                snapshot.status = "active"
                snapshot.provider_payment_id = payment_entity.get("id")
                await apply_subscription_update(
                    db, organization_id=org_id, snapshot=snapshot
                )

        elif etype in {"payment.failed", "subscription.halted"}:
            entity = sub_entity or {
                "id": payment_entity.get("subscription_id"),
                "customer_id": payment_entity.get("customer_id"),
                "status": "halted",
                "notes": payment_entity.get("notes") or {},
            }
            org_id = await self._org_id_from_entity(db, entity)
            if org_id:
                sub = (
                    await db.execute(
                        select(Subscription).where(
                            Subscription.organization_id == org_id
                        )
                    )
                ).scalar_one_or_none()
                if sub:
                    sub.status = "past_due"
                    if payment_entity.get("id"):
                        sub.provider_payment_id = payment_entity["id"]
                    await db.flush()

        elif etype in {"invoice.paid", "invoice.partially_paid"} and invoice_entity:
            cust = invoice_entity.get("customer_id")
            org = await find_org_by_customer_id(
                db, provider=self.name, customer_id=cust or ""
            )
            if not org and invoice_entity.get("subscription_id"):
                sub = (
                    await db.execute(
                        select(Subscription).where(
                            Subscription.provider_subscription_id
                            == invoice_entity["subscription_id"]
                        )
                    )
                ).scalar_one_or_none()
                if sub:
                    org = (
                        await db.execute(
                            select(Organization).where(
                                Organization.id == sub.organization_id
                            )
                        )
                    ).scalar_one_or_none()
            if org:
                # Razorpay amounts are in paise
                amount_paid = (invoice_entity.get("amount_paid") or 0) / 100.0
                amount_due = (invoice_entity.get("amount") or 0) / 100.0
                paid_at = None
                if invoice_entity.get("paid_at"):
                    paid_at = datetime.fromtimestamp(
                        int(invoice_entity["paid_at"]), tz=timezone.utc
                    )
                await record_normalized_invoice(
                    db,
                    org.id,
                    NormalizedInvoice(
                        provider=self.name,
                        provider_invoice_id=invoice_entity.get("id") or "",
                        status=invoice_entity.get("status") or "paid",
                        amount_due=amount_due,
                        amount_paid=amount_paid,
                        currency=(invoice_entity.get("currency") or "inr").lower(),
                        number=invoice_entity.get("receipt")
                        or invoice_entity.get("id"),
                        hosted_invoice_url=invoice_entity.get("short_url"),
                        paid_at=paid_at,
                    ),
                )

        await db.commit()
        return {"status": "ok", "type": etype, "provider": self.name}
