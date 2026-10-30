"""Billing, subscriptions, lifecycle, usage, and provider webhooks."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from app.api.deps.auth import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.billing import Invoice
from app.models.organization import OrganizationMember
from app.schemas.billing import (
    ChangePlanRequest,
    CheckoutRequest,
    CheckoutResponse,
    InvoiceResponse,
    LifecycleActionResponse,
    PortalResponse,
    PricingCatalogResponse,
    SubscriptionResponse,
    UsageResponse,
)
from app.services.billing import BillingNotConfigured, get_billing_provider
from app.services.billing.factory import BillingProviderFactory
from app.services.billing.lifecycle import (
    apply_due_pending_changes,
    cancel_subscription,
    change_plan,
    clear_scheduled_downgrade,
    display_plan,
    plan_rank,
    reactivate_subscription,
)
from app.services.billing.soft_limits import count_active_repositories
from app.services.organizations import get_active_organization, get_user_membership
from app.services.plans import FEATURE_COMPARISON, PRICING_CATALOG, PAID_PLANS, get_plan_limits
from app.services import entitlements as entitlement_service

router = APIRouter()
settings = get_settings()
logger = get_logger(__name__)


def _price_for_plan(plan: str) -> tuple[float | None, str | None]:
    for row in PRICING_CATALOG:
        if row.get("id") == plan:
            return row.get("monthly_price"), row.get("price_label")
    return None, None


def _pending_message(sub, plan: str) -> str | None:
    if not sub or not sub.pending_plan:
        if sub and sub.cancel_at_period_end and sub.current_period_end:
            return (
                f"Your {display_plan(plan)} subscription will end on "
                f"{sub.current_period_end.strftime('%B %d, %Y')}. "
                "You'll move to Evaluation afterward — all data is kept."
            )
        return None
    effective = sub.pending_change_effective_at or sub.current_period_end
    when = effective.strftime("%B %d, %Y") if effective else "the end of your billing period"
    if sub.pending_change_type == "cancel" or sub.pending_plan == "free":
        return (
            f"Your {display_plan(plan)} subscription will end on {when}. "
            "You'll move to Evaluation afterward — all data is kept."
        )
    return (
        f"Your subscription will change from {display_plan(plan)} to "
        f"{display_plan(sub.pending_plan)} on {when}."
    )


async def _require_billing_admin(db: DbSession, current_user: CurrentUser):
    org = await get_active_organization(db, current_user)
    membership = await get_user_membership(db, current_user.id, org.id)
    if membership is None or membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only owners/admins can manage billing")
    return org


def _to_lifecycle_response(result) -> LifecycleActionResponse:
    return LifecycleActionResponse(
        action=result.action,
        plan=result.plan,
        pending_plan=result.pending_plan,
        pending_change_type=result.pending_change_type,
        pending_change_effective_at=result.pending_change_effective_at,
        cancel_at_period_end=result.cancel_at_period_end,
        current_period_end=result.current_period_end,
        message=result.message,
        checkout_url=result.checkout_url,
        mode=result.mode,
        provider=result.provider,
        soft_limit_summary=result.soft_limit_summary,
    )


@router.get("/pricing", response_model=PricingCatalogResponse)
async def pricing_catalog() -> PricingCatalogResponse:
    provider = get_billing_provider()
    pub = provider.publishable_key()
    return PricingCatalogResponse(
        plans=PRICING_CATALOG,
        feature_comparison=FEATURE_COMPARISON,
        billing_provider=provider.name,
        publishable_key=pub,
        stripe_publishable_key=pub if provider.name == "stripe" else None,
    )


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(db: DbSession, current_user: CurrentUser) -> SubscriptionResponse:
    org = await get_active_organization(db, current_user)
    # Opportunistically apply due period-end transitions
    await apply_due_pending_changes(db, org=org, actor=current_user)
    entitlements = await entitlement_service.get_entitlements(db, org)
    sub = await entitlement_service.get_org_subscription(db, org)
    limits = get_plan_limits(org.plan)
    migration_stats = await entitlement_service.sum_migration_usage_month(
        db, organization_id=org.id
    )
    price_monthly, price_label = _price_for_plan(org.plan)
    plan = (org.plan or "free").lower()
    can_reactivate = bool(
        sub
        and (
            sub.cancel_at_period_end
            or sub.pending_change_type == "cancel"
            or (sub.pending_plan == "free")
            or sub.pending_change_type == "downgrade"
        )
    )
    await db.commit()
    return SubscriptionResponse(
        plan=plan,
        status=entitlements.status,
        billing_interval=sub.billing_interval if sub else "month",
        seat_count=sub.seat_count if sub else 1,
        trial_ends_at=entitlements.trial_ends_at,
        trial_active=entitlements.trial_active,
        evaluation_active=entitlements.evaluation_active,
        evaluation_expired=entitlements.evaluation_expired,
        read_only=entitlements.read_only,
        can_write=entitlements.can_write,
        can_import_repositories=entitlements.can_import_repositories,
        can_trigger_scans=entitlements.can_trigger_scans,
        can_sync_repositories=entitlements.can_sync_repositories,
        can_run_background_jobs=entitlements.can_run_background_jobs,
        current_period_start=sub.current_period_start if sub else None,
        current_period_end=sub.current_period_end if sub else None,
        cancel_at_period_end=bool(sub.cancel_at_period_end) if sub else False,
        pending_plan=sub.pending_plan if sub else None,
        pending_interval=sub.pending_interval if sub else None,
        pending_change_type=sub.pending_change_type if sub else None,
        pending_change_effective_at=sub.pending_change_effective_at if sub else None,
        pending_change_message=_pending_message(sub, plan),
        can_upgrade=plan != "enterprise",
        can_downgrade=plan in PAID_PLANS and plan != "starter",
        can_cancel=plan in PAID_PLANS and not (sub and sub.cancel_at_period_end),
        can_reactivate=can_reactivate,
        billing_provider=(sub.billing_provider if sub else None)
        or org.billing_provider
        or get_billing_provider().name,
        next_invoice_at=sub.current_period_end if sub and plan in PAID_PLANS else None,
        upgrade_simulator=entitlements.upgrade_simulator,
        ai_enabled=entitlements.ai_enabled,
        ai_migration_assistant=entitlements.ai_migration_assistant,
        can_generate_ai_migration=entitlements.can_generate_ai_migration,
        can_view_ai_migration_reports=entitlements.can_view_ai_migration_reports,
        ai_migration_requests_this_month=migration_stats["requests"],
        ai_migration_tokens_this_month=migration_stats["tokens"],
        ai_migration_cost_this_month=migration_stats["estimated_cost_usd"],
        price_monthly=price_monthly,
        price_label=price_label,
        limits={
            "max_users": limits.max_users,
            "max_repositories": limits.max_repositories,
            "monthly_scan_limit": limits.monthly_scan_limit,
            "upgrade_simulator": entitlements.upgrade_simulator,
            "ai_enabled": entitlements.ai_enabled,
            "ai_migration_assistant": entitlements.ai_migration_assistant,
            "teams_enabled": entitlements.teams_enabled,
            "rbac": entitlements.rbac,
            "scheduled_scans": entitlements.scheduled_scans,
            "api_access": entitlements.api_access,
            "webhooks": entitlements.webhooks,
            "export_reports": entitlements.export_reports,
            "audit_logs": limits.audit_logs,
            "can_write": entitlements.can_write,
            "evaluation_expired": entitlements.evaluation_expired,
            "read_only": entitlements.read_only,
        },
    )


@router.get("/usage", response_model=UsageResponse)
async def get_usage(db: DbSession, current_user: CurrentUser) -> UsageResponse:
    org = await get_active_organization(db, current_user)
    entitlements = await entitlement_service.get_entitlements(db, org)
    limits = get_plan_limits(org.plan)
    repos = await count_active_repositories(db, organization_id=org.id)
    if not repos and org.owner_user_id:
        repos = await count_active_repositories(db, owner_id=current_user.id)
    members = await db.scalar(
        select(func.count()).select_from(OrganizationMember).where(
            OrganizationMember.organization_id == org.id
        )
    )
    migration_stats = await entitlement_service.sum_migration_usage_month(
        db, organization_id=org.id
    )
    scans_used = await entitlement_service.count_scans_this_month(
        db, org=org, owner_user_id=current_user.id
    )
    await db.commit()
    return UsageResponse(
        plan=org.plan,
        repositories_used=int(repos or 0),
        repositories_limit=limits.max_repositories,
        members_used=int(members or 0),
        members_limit=limits.max_users,
        monthly_scan_limit=limits.monthly_scan_limit,
        monthly_scans_used=scans_used,
        evaluation_active=entitlements.evaluation_active,
        evaluation_expired=entitlements.evaluation_expired,
        read_only=entitlements.read_only,
        can_write=entitlements.can_write,
        upgrade_simulator=entitlements.upgrade_simulator,
        ai_enabled=entitlements.ai_enabled,
        ai_migration_assistant=entitlements.ai_migration_assistant,
        can_generate_ai_migration=entitlements.can_generate_ai_migration,
        ai_migration_requests_this_month=migration_stats["requests"],
        ai_migration_tokens_this_month=migration_stats["tokens"],
        ai_migration_cost_this_month=migration_stats["estimated_cost_usd"],
        ai_migration_avg_ms=migration_stats["avg_execution_time_ms"],
        teams_enabled=entitlements.teams_enabled,
        api_access=entitlements.api_access,
        scheduled_scans=entitlements.scheduled_scans,
        webhooks=entitlements.webhooks,
        rbac=entitlements.rbac,
        audit_logs=limits.audit_logs,
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    db: DbSession,
    current_user: CurrentUser,
    body: CheckoutRequest,
) -> CheckoutResponse:
    org = await _require_billing_admin(db, current_user)
    success = body.success_url or f"{settings.app_url}/billing?checkout=success"
    cancel = body.cancel_url or f"{settings.app_url}/billing?checkout=cancel"
    provider = get_billing_provider()
    # Prefer lifecycle for upgrades when already on a paid plan
    current = (org.plan or "free").lower()
    if current in PAID_PLANS and plan_rank(body.plan) > plan_rank(current):
        try:
            result = await change_plan(
                db,
                org=org,
                target_plan=body.plan,
                interval=body.interval,
                actor=current_user,
                success_url=success,
                cancel_url=cancel,
            )
        except BillingNotConfigured as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        await db.commit()
        if result.checkout_url:
            return CheckoutResponse(
                url=result.checkout_url,
                session_id=f"lifecycle_{org.id.hex[:12]}",
                mode=result.mode,
                provider=result.provider,
            )
        return CheckoutResponse(
            url=success,
            session_id=f"lifecycle_{org.id.hex[:12]}",
            mode=result.mode,
            provider=result.provider,
        )
    try:
        result = await provider.create_checkout_session(
            db,
            org=org,
            plan=body.plan,
            interval=body.interval,
            success_url=success,
            cancel_url=cancel,
            customer_email=current_user.email,
        )
        await db.commit()
    except BillingNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("checkout_failed", error=str(exc), provider=provider.name)
        raise HTTPException(
            status_code=502,
            detail="Billing provider error. Check gateway credentials and plan/price IDs.",
        ) from exc
    return CheckoutResponse(
        url=result.url,
        session_id=result.session_id,
        mode=result.mode,
        provider=result.provider or provider.name,
    )


@router.post("/change-plan", response_model=LifecycleActionResponse)
async def change_plan_endpoint(
    db: DbSession,
    current_user: CurrentUser,
    body: ChangePlanRequest,
) -> LifecycleActionResponse:
    """Upgrade immediately or schedule a downgrade at period end."""
    org = await _require_billing_admin(db, current_user)
    try:
        result = await change_plan(
            db,
            org=org,
            target_plan=body.plan,
            interval=body.interval,
            actor=current_user,
            success_url=body.success_url or f"{settings.app_url}/billing?checkout=success",
            cancel_url=body.cancel_url or f"{settings.app_url}/billing?checkout=cancel",
        )
        await db.commit()
    except BillingNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_lifecycle_response(result)


@router.post("/cancel", response_model=LifecycleActionResponse)
async def cancel_plan_endpoint(
    db: DbSession,
    current_user: CurrentUser,
) -> LifecycleActionResponse:
    org = await _require_billing_admin(db, current_user)
    result = await cancel_subscription(db, org=org, actor=current_user)
    await db.commit()
    return _to_lifecycle_response(result)


@router.post("/reactivate", response_model=LifecycleActionResponse)
async def reactivate_plan_endpoint(
    db: DbSession,
    current_user: CurrentUser,
) -> LifecycleActionResponse:
    org = await _require_billing_admin(db, current_user)
    result = await reactivate_subscription(db, org=org, actor=current_user)
    await db.commit()
    return _to_lifecycle_response(result)


@router.post("/clear-pending", response_model=LifecycleActionResponse)
async def clear_pending_endpoint(
    db: DbSession,
    current_user: CurrentUser,
) -> LifecycleActionResponse:
    """Clear a scheduled downgrade (keep current plan)."""
    org = await _require_billing_admin(db, current_user)
    result = await clear_scheduled_downgrade(db, org=org)
    await db.commit()
    return _to_lifecycle_response(result)


@router.post("/portal", response_model=PortalResponse)
async def create_portal(db: DbSession, current_user: CurrentUser) -> PortalResponse:
    org = await _require_billing_admin(db, current_user)
    provider = get_billing_provider()
    try:
        result = await provider.create_customer_portal(
            db, org=org, return_url=f"{settings.app_url}/billing"
        )
    except BillingNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await db.commit()
    return PortalResponse(
        url=result.url,
        mode=result.mode,
        provider=result.provider or provider.name,
    )


@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(db: DbSession, current_user: CurrentUser) -> list[InvoiceResponse]:
    org = await get_active_organization(db, current_user)
    result = await db.execute(
        select(Invoice)
        .where(Invoice.organization_id == org.id)
        .order_by(Invoice.created_at.desc())
        .limit(50)
    )
    await db.commit()
    return [
        InvoiceResponse(
            id=i.id,
            number=i.number,
            status=i.status,
            amount_due=float(i.amount_due or 0),
            amount_paid=float(i.amount_paid or 0),
            currency=i.currency,
            hosted_invoice_url=i.hosted_invoice_url,
            invoice_pdf=i.invoice_pdf,
            paid_at=i.paid_at,
            created_at=i.created_at,
        )
        for i in result.scalars().all()
    ]


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: DbSession) -> dict:
    """Stripe-only webhook — never routed to other providers."""
    payload = await request.body()
    provider = BillingProviderFactory.for_webhook("stripe")
    try:
        return await provider.handle_webhook(db, payload, dict(request.headers))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, db: DbSession) -> dict:
    """Razorpay-only webhook — never routed to other providers."""
    payload = await request.body()
    provider = BillingProviderFactory.for_webhook("razorpay")
    try:
        return await provider.handle_webhook(db, payload, dict(request.headers))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
