"""Enterprise subscription lifecycle — upgrade / downgrade / cancel / reactivate.

SaaS rules (GitHub / Vercel / Linear / Notion style):
  • Upgrades are immediate (provider proration when available)
  • Downgrades are scheduled for period end — current entitlements stay
  • Cancellation is cancel_at_period_end — access until renewal, then Evaluation
  • Reactivate clears pending cancellation and keeps the billing cycle
  • Plan reductions never delete customer data (soft limits only)

Provider-specific calls stay inside BillingProvider implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.billing import Subscription
from app.models.organization import Organization
from app.models.user import User
from app.services.billing.base import BillingNotConfigured, NormalizedSubscription
from app.services.billing.factory import get_billing_provider
from app.services.billing.soft_limits import enforce_plan_soft_limits
from app.services.billing.sync import activate_plan_local, apply_subscription_update
from app.services.plans import CHECKOUT_PLANS, PAID_PLANS, get_plan_limits

logger = get_logger(__name__)


def _forbid_local_paid_activation() -> None:
    """Never grant a paid plan in production without the billing provider."""
    if get_settings().is_production:
        raise BillingNotConfigured(
            "Paid plan activation requires a configured billing provider in production."
        )


PLAN_RANK: dict[str, int] = {
    "free": 0,
    "starter": 1,
    "pro": 2,
    "team": 3,
    "enterprise": 4,
}

ChangeKind = Literal["upgrade", "downgrade", "same", "cancel"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def plan_rank(plan: str) -> int:
    return PLAN_RANK.get((plan or "free").lower(), 0)


def classify_change(current: str, target: str) -> ChangeKind:
    cur, tgt = (current or "free").lower(), (target or "free").lower()
    if tgt == "free" and cur in PAID_PLANS:
        return "cancel"
    if plan_rank(tgt) > plan_rank(cur):
        return "upgrade"
    if plan_rank(tgt) < plan_rank(cur):
        return "downgrade"
    return "same"


def display_plan(plan: str) -> str:
    return get_plan_limits(plan).display_name


@dataclass
class LifecycleResult:
    action: str
    plan: str
    pending_plan: Optional[str] = None
    pending_change_type: Optional[str] = None
    pending_change_effective_at: Optional[datetime] = None
    cancel_at_period_end: bool = False
    current_period_end: Optional[datetime] = None
    message: str = ""
    checkout_url: Optional[str] = None
    mode: str = "local"
    provider: str = "local"
    soft_limit_summary: Optional[dict[str, Any]] = None


def clear_pending_change(sub: Subscription) -> None:
    sub.pending_plan = None
    sub.pending_interval = None
    sub.pending_change_type = None
    sub.pending_change_effective_at = None


def schedule_pending_change(
    sub: Subscription,
    *,
    plan: str,
    interval: str,
    change_type: str,
    effective_at: Optional[datetime],
) -> None:
    sub.pending_plan = plan
    sub.pending_interval = interval
    sub.pending_change_type = change_type
    sub.pending_change_effective_at = effective_at


def _period_end(sub: Optional[Subscription]) -> datetime:
    if sub and sub.current_period_end:
        end = _aware(sub.current_period_end)
        if end and end > _utcnow():
            return end
    # Sensible default when provider hasn't synced a period yet
    interval = (sub.billing_interval if sub else "month") or "month"
    return _utcnow() + timedelta(days=365 if interval == "year" else 30)


async def get_or_create_subscription(
    db: AsyncSession, org: Organization
) -> Subscription:
    sub = (
        await db.execute(
            select(Subscription).where(Subscription.organization_id == org.id)
        )
    ).scalar_one_or_none()
    if sub is None:
        sub = Subscription(
            organization_id=org.id,
            plan=org.plan or "free",
            status="active",
            billing_interval="month",
            seat_count=1,
        )
        db.add(sub)
        await db.flush()
    return sub


async def change_plan(
    db: AsyncSession,
    *,
    org: Organization,
    target_plan: str,
    interval: str = "month",
    actor: Optional[User] = None,
    success_url: Optional[str] = None,
    cancel_url: Optional[str] = None,
) -> LifecycleResult:
    """Upgrade immediately or schedule a downgrade at period end."""
    target = (target_plan or "").lower()
    interval = "year" if interval == "year" else "month"
    current = (org.plan or "free").lower()

    if target == "enterprise":
        raise ValueError("Enterprise plans are sold via Contact Sales")
    if target not in CHECKOUT_PLANS and target != "free":
        raise ValueError("Unsupported plan")

    kind = classify_change(current, target)
    if kind == "same":
        sub = await get_or_create_subscription(db, org)
        return LifecycleResult(
            action="noop",
            plan=current,
            pending_plan=sub.pending_plan,
            pending_change_type=sub.pending_change_type,
            pending_change_effective_at=sub.pending_change_effective_at,
            cancel_at_period_end=bool(sub.cancel_at_period_end),
            current_period_end=sub.current_period_end,
            message=f"Already on {display_plan(current)}.",
            provider=sub.billing_provider or "local",
        )

    if kind == "cancel" or target == "free":
        return await cancel_subscription(db, org=org, actor=actor)

    if kind == "upgrade":
        return await _upgrade(
            db,
            org=org,
            target=target,
            interval=interval,
            actor=actor,
            success_url=success_url,
            cancel_url=cancel_url,
        )

    return await _schedule_downgrade(
        db, org=org, target=target, interval=interval, actor=actor
    )


async def _upgrade(
    db: AsyncSession,
    *,
    org: Organization,
    target: str,
    interval: str,
    actor: Optional[User],
    success_url: Optional[str],
    cancel_url: Optional[str],
) -> LifecycleResult:
    provider = get_billing_provider()
    sub = await get_or_create_subscription(db, org)
    has_provider_sub = bool(sub.provider_subscription_id or sub.stripe_subscription_id)
    paid_active = (sub.status or "").lower() in {
        "active",
        "trialing",
        "authenticated",
        "past_due",
    }

    # Clear any scheduled downgrade / cancel when upgrading
    clear_pending_change(sub)
    sub.cancel_at_period_end = False

    if has_provider_sub and paid_active and provider.is_configured():
        try:
            await provider.update_subscription(
                db,
                org=org,
                plan=target,
                interval=interval,
                schedule_change_at="now",
            )
            await db.refresh(sub)
            await db.refresh(org)
            return LifecycleResult(
                action="upgraded",
                plan=org.plan,
                cancel_at_period_end=False,
                current_period_end=sub.current_period_end,
                message=(
                    f"Upgraded to {display_plan(org.plan)}. "
                    "New entitlements are active immediately."
                ),
                mode="provider",
                provider=provider.name,
            )
        except (NotImplementedError, ValueError, RuntimeError) as exc:
            logger.warning(
                "provider_upgrade_fallback",
                provider=provider.name,
                error=str(exc),
            )

    # No existing subscription → checkout (or local activate)
    if not provider.is_configured() or not has_provider_sub:
        # Prefer checkout when configured and no sub; local when not configured
        if provider.is_configured() and not has_provider_sub:
            from app.core.config import get_settings

            settings = get_settings()
            result = await provider.create_checkout_session(
                db,
                org=org,
                plan=target,
                interval=interval,
                success_url=success_url
                or f"{settings.app_url}/billing?checkout=success",
                cancel_url=cancel_url
                or f"{settings.app_url}/billing?checkout=cancel",
                customer_email=actor.email if actor else None,
            )
            # Dev/local checkout may have already activated
            await db.refresh(org)
            await db.refresh(sub)
            if result.mode in {"dev", "local"} or org.plan == target:
                return LifecycleResult(
                    action="upgraded",
                    plan=org.plan,
                    current_period_end=sub.current_period_end,
                    message=f"Upgraded to {display_plan(org.plan)}.",
                    checkout_url=result.url,
                    mode=result.mode,
                    provider=result.provider or provider.name,
                )
            return LifecycleResult(
                action="checkout_required",
                plan=org.plan,
                message="Complete checkout to activate the new plan.",
                checkout_url=result.url,
                mode=result.mode,
                provider=result.provider or provider.name,
            )

        _forbid_local_paid_activation()
        await activate_plan_local(
            db, org, plan=target, interval=interval, trial_days=0, provider="local"
        )
        clear_pending_change(sub)
        sub.cancel_at_period_end = False
        await db.flush()
        return LifecycleResult(
            action="upgraded",
            plan=org.plan,
            current_period_end=sub.current_period_end,
            message=f"Upgraded to {display_plan(org.plan)}. Entitlements unlocked.",
            mode="local",
            provider="local",
        )

    # Configured + has sub but update failed path already fell through
    _forbid_local_paid_activation()
    await activate_plan_local(
        db, org, plan=target, interval=interval, trial_days=0, provider="local"
    )
    clear_pending_change(sub)
    return LifecycleResult(
        action="upgraded",
        plan=org.plan,
        message=f"Upgraded to {display_plan(org.plan)}.",
        mode="local",
        provider=provider.name,
    )


async def _schedule_downgrade(
    db: AsyncSession,
    *,
    org: Organization,
    target: str,
    interval: str,
    actor: Optional[User],
) -> LifecycleResult:
    del actor  # reserved for audit wiring
    provider = get_billing_provider()
    sub = await get_or_create_subscription(db, org)
    keep_plan = (org.plan or "free").lower()
    effective = _period_end(sub)

    meta = dict(sub.extra_metadata or {})
    meta["pre_downgrade_plan"] = keep_plan
    sub.extra_metadata = meta

    schedule_pending_change(
        sub,
        plan=target,
        interval=interval or sub.billing_interval or "month",
        change_type="downgrade",
        effective_at=effective,
    )
    sub.cancel_at_period_end = False

    has_provider_sub = bool(sub.provider_subscription_id or sub.stripe_subscription_id)
    if has_provider_sub and provider.is_configured():
        try:
            await provider.update_subscription(
                db,
                org=org,
                plan=target,
                interval=interval,
                schedule_change_at="period_end",
            )
        except (NotImplementedError, ValueError, RuntimeError) as exc:
            logger.info(
                "provider_schedule_downgrade_local",
                provider=provider.name,
                error=str(exc),
            )

    # Entitlements stay on the current plan until the effective date.
    org.plan = keep_plan
    sub.plan = keep_plan
    # Re-assert pending (provider sync may have cleared it)
    schedule_pending_change(
        sub,
        plan=target,
        interval=interval or sub.billing_interval or "month",
        change_type="downgrade",
        effective_at=effective,
    )
    sub.cancel_at_period_end = False
    await db.flush()

    effective_label = effective.strftime("%B %d, %Y")
    return LifecycleResult(
        action="downgrade_scheduled",
        plan=org.plan,
        pending_plan=sub.pending_plan,
        pending_change_type=sub.pending_change_type,
        pending_change_effective_at=sub.pending_change_effective_at,
        cancel_at_period_end=False,
        current_period_end=sub.current_period_end,
        message=(
            f"Your subscription will change from {display_plan(keep_plan)} to "
            f"{display_plan(target)} on {effective_label}."
        ),
        mode="scheduled",
        provider=sub.billing_provider or provider.name,
    )


async def cancel_subscription(
    db: AsyncSession,
    *,
    org: Organization,
    actor: Optional[User] = None,
    immediate: bool = False,
) -> LifecycleResult:
    """Schedule cancellation at period end (default) → Evaluation after expiry."""
    if (org.plan or "free").lower() == "free":
        sub = await get_or_create_subscription(db, org)
        return LifecycleResult(
            action="noop",
            plan="free",
            message="Already on Evaluation.",
            provider=sub.billing_provider or "local",
        )

    provider = get_billing_provider()
    sub = await get_or_create_subscription(db, org)
    effective = _period_end(sub)

    if immediate:
        # Rare — admin/dev. Prefer period-end for customers.
        org.plan = "free"
        sub.plan = "free"
        sub.status = "canceled"
        sub.cancel_at_period_end = False
        sub.canceled_at = _utcnow()
        clear_pending_change(sub)
        summary = await enforce_plan_soft_limits(db, org, actor=actor)
        await db.flush()
        return LifecycleResult(
            action="canceled",
            plan="free",
            message="Subscription canceled. Workspace moved to Evaluation.",
            soft_limit_summary=summary,
            provider=sub.billing_provider or provider.name,
        )

    sub.cancel_at_period_end = True
    schedule_pending_change(
        sub,
        plan="free",
        interval=sub.billing_interval or "month",
        change_type="cancel",
        effective_at=effective,
    )
    # Keep paid entitlements until period end
    meta = dict(sub.extra_metadata or {})
    meta["pre_cancel_plan"] = org.plan
    sub.extra_metadata = meta

    has_provider_sub = bool(sub.provider_subscription_id or sub.stripe_subscription_id)
    if has_provider_sub and provider.is_configured():
        try:
            await provider.cancel_subscription(
                db, org=org, cancel_at_period_end=True
            )
        except (NotImplementedError, ValueError, RuntimeError) as exc:
            logger.info("provider_cancel_local", provider=provider.name, error=str(exc))

    await db.flush()
    return LifecycleResult(
        action="cancel_scheduled",
        plan=org.plan,
        pending_plan="free",
        pending_change_type="cancel",
        pending_change_effective_at=effective,
        cancel_at_period_end=True,
        current_period_end=sub.current_period_end or effective,
        message=(
            f"Your {display_plan(org.plan)} subscription will end on "
            f"{effective.strftime('%B %d, %Y')}. "
            "You'll move to Evaluation afterward — all data is kept."
        ),
        provider=sub.billing_provider or provider.name,
    )


async def reactivate_subscription(
    db: AsyncSession,
    *,
    org: Organization,
    actor: Optional[User] = None,
) -> LifecycleResult:
    """Undo pending cancellation / scheduled downgrade to free; keep billing cycle."""
    provider = get_billing_provider()
    sub = await get_or_create_subscription(db, org)

    if not sub.cancel_at_period_end and not (
        sub.pending_change_type == "cancel" or sub.pending_plan == "free"
    ):
        # Allow clearing a scheduled downgrade via reactivate? Prefer explicit cancel of pending.
        if sub.pending_plan and sub.pending_change_type == "downgrade":
            clear_pending_change(sub)
            await db.flush()
            return LifecycleResult(
                action="pending_cleared",
                plan=org.plan,
                message=f"Scheduled plan change canceled. You remain on {display_plan(org.plan)}.",
                current_period_end=sub.current_period_end,
                provider=sub.billing_provider or provider.name,
            )
        return LifecycleResult(
            action="noop",
            plan=org.plan,
            message="No pending cancellation to reactivate.",
            cancel_at_period_end=False,
            current_period_end=sub.current_period_end,
            provider=sub.billing_provider or provider.name,
        )

    sub.cancel_at_period_end = False
    sub.canceled_at = None
    if sub.pending_change_type == "cancel" or sub.pending_plan == "free":
        clear_pending_change(sub)

    has_provider_sub = bool(sub.provider_subscription_id or sub.stripe_subscription_id)
    if has_provider_sub and provider.is_configured():
        try:
            await provider.resume_subscription(db, org=org)
        except (NotImplementedError, ValueError, RuntimeError) as exc:
            logger.info("provider_resume_local", provider=provider.name, error=str(exc))

    await db.flush()
    return LifecycleResult(
        action="reactivated",
        plan=org.plan,
        cancel_at_period_end=False,
        current_period_end=sub.current_period_end,
        message=(
            f"Subscription reactivated. You remain on {display_plan(org.plan)} "
            "for the current billing cycle."
        ),
        provider=sub.billing_provider or provider.name,
    )


async def clear_scheduled_downgrade(
    db: AsyncSession,
    *,
    org: Organization,
) -> LifecycleResult:
    """Cancel a scheduled downgrade; stay on current plan."""
    sub = await get_or_create_subscription(db, org)
    if not sub.pending_plan or sub.pending_change_type != "downgrade":
        return LifecycleResult(
            action="noop",
            plan=org.plan,
            message="No scheduled downgrade.",
            provider=sub.billing_provider or "local",
        )
    clear_pending_change(sub)
    await db.flush()
    return LifecycleResult(
        action="pending_cleared",
        plan=org.plan,
        message=f"Scheduled downgrade canceled. You remain on {display_plan(org.plan)}.",
        current_period_end=sub.current_period_end,
        provider=sub.billing_provider or "local",
    )


async def apply_due_pending_changes(
    db: AsyncSession,
    *,
    org: Organization,
    actor: Optional[User] = None,
) -> Optional[LifecycleResult]:
    """Apply pending downgrade/cancel when effective_at has passed. Data-safe."""
    sub = (
        await db.execute(
            select(Subscription).where(Subscription.organization_id == org.id)
        )
    ).scalar_one_or_none()
    if sub is None or not sub.pending_plan:
        # Also honor cancel_at_period_end without pending_plan (provider-driven)
        if (
            sub
            and sub.cancel_at_period_end
            and sub.current_period_end
            and _aware(sub.current_period_end) <= _utcnow()
            and (org.plan or "").lower() in PAID_PLANS
        ):
            return await _apply_transition_to_plan(
                db, org=org, sub=sub, target="free", change_type="cancel", actor=actor
            )
        return None

    effective = _aware(sub.pending_change_effective_at) or _aware(sub.current_period_end)
    if effective and effective > _utcnow():
        return None

    target = (sub.pending_plan or "free").lower()
    change_type = sub.pending_change_type or (
        "cancel" if target == "free" else "downgrade"
    )
    return await _apply_transition_to_plan(
        db,
        org=org,
        sub=sub,
        target=target,
        change_type=change_type,
        actor=actor,
        interval=sub.pending_interval or sub.billing_interval or "month",
    )


async def _apply_transition_to_plan(
    db: AsyncSession,
    *,
    org: Organization,
    sub: Subscription,
    target: str,
    change_type: str,
    actor: Optional[User] = None,
    interval: str = "month",
) -> LifecycleResult:
    provider = get_billing_provider()
    previous = org.plan

    if target == "free" or change_type == "cancel":
        org.plan = "free"
        sub.plan = "free"
        sub.status = "canceled"
        sub.cancel_at_period_end = False
        sub.canceled_at = sub.canceled_at or _utcnow()
        clear_pending_change(sub)
        summary = await enforce_plan_soft_limits(db, org, actor=actor)
        await db.flush()
        logger.info(
            "lifecycle_transitioned_to_evaluation",
            organization_id=str(org.id),
            previous_plan=previous,
        )
        return LifecycleResult(
            action="transitioned",
            plan="free",
            message="Subscription ended. Workspace is on Evaluation — all data retained.",
            soft_limit_summary=summary,
            provider=sub.billing_provider or provider.name,
        )

    # Downgrade to a paid lower plan
    has_provider_sub = bool(sub.provider_subscription_id or sub.stripe_subscription_id)
    if has_provider_sub and provider.is_configured():
        try:
            await provider.update_subscription(
                db,
                org=org,
                plan=target,
                interval=interval,
                schedule_change_at="now",
            )
        except (NotImplementedError, ValueError, RuntimeError) as exc:
            logger.warning("apply_downgrade_provider_failed", error=str(exc))
            org.plan = target
            sub.plan = target
    else:
        org.plan = target
        sub.plan = target
        sub.billing_interval = interval

    clear_pending_change(sub)
    sub.cancel_at_period_end = False
    summary = await enforce_plan_soft_limits(db, org, actor=actor)
    await db.flush()
    logger.info(
        "lifecycle_downgrade_applied",
        organization_id=str(org.id),
        previous_plan=previous,
        plan=target,
        archived=len((summary or {}).get("archived_repository_ids") or []),
    )
    return LifecycleResult(
        action="downgraded",
        plan=org.plan,
        message=(
            f"Plan changed from {display_plan(previous)} to {display_plan(org.plan)}. "
            "Excess repositories were archived — nothing was deleted."
        ),
        soft_limit_summary=summary,
        provider=sub.billing_provider or provider.name,
    )


async def apply_due_for_all_orgs(db: AsyncSession, *, limit: int = 200) -> int:
    """Batch job helper — process orgs with due pending changes."""
    now = _utcnow()
    rows = (
        await db.execute(
            select(Subscription)
            .where(Subscription.pending_plan.is_not(None))
            .where(
                (Subscription.pending_change_effective_at.is_(None))
                | (Subscription.pending_change_effective_at <= now)
            )
            .limit(limit)
        )
    ).scalars().all()
    count = 0
    for sub in rows:
        org = (
            await db.execute(
                select(Organization).where(Organization.id == sub.organization_id)
            )
        ).scalar_one_or_none()
        if org is None:
            continue
        result = await apply_due_pending_changes(db, org=org)
        if result:
            count += 1
    return count
