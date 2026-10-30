"""Subscription-aware feature entitlements.

Backend is the source of truth — never rely on the frontend alone.

Evaluation (plan=free) — 7 days from account/org creation, no credit card.
  Active: write access + Upgrade Simulator + limited scans
  Expired: read-only (view data); no imports/scans/sync/jobs/simulator

Starter / Pro / Team / Enterprise — paid (or Stripe-trialing) access.

Upgrade Simulator (analysis)     → Evaluation (active) + paid plans
AI Upgrade Advisor / summaries → Pro+
AI Migration Assistant (code)  → Team / Enterprise only

Never merge Upgrade Simulator and AI Migration Assistant.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import FeatureUsageEvent, Subscription
from app.models.organization import Organization
from app.services.plans import (
    FEATURE_AI,
    FEATURE_AI_MIGRATION,
    FEATURE_UPGRADE_SIMULATOR,
    PAID_PLANS,
    TEAM_PLANS,
    TRIAL_DAYS,
    get_plan_limits,
    require_feature,
)


@dataclass(frozen=True)
class EntitlementSnapshot:
    plan: str
    status: str
    trial_active: bool
    trial_ends_at: Optional[datetime]
    evaluation_active: bool
    evaluation_expired: bool
    read_only: bool
    can_write: bool
    can_import_repositories: bool
    can_trigger_scans: bool
    can_sync_repositories: bool
    can_run_background_jobs: bool
    upgrade_simulator: bool
    ai_enabled: bool
    ai_migration_assistant: bool
    teams_enabled: bool
    rbac: bool
    api_access: bool
    scheduled_scans: bool
    webhooks: bool
    export_reports: bool
    can_generate_ai_migration: bool
    can_view_ai_migration_reports: bool  # historical reports stay visible
    monthly_scan_limit: Optional[int]
    max_repositories: Optional[int]
    max_users: Optional[int]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def evaluation_ends_at(org: Organization, sub: Optional[Subscription]) -> Optional[datetime]:
    """Resolve the evaluation end timestamp for a free-plan org."""
    if (org.plan or "free").lower() != "free":
        return None
    if sub and sub.trial_ends_at:
        return _aware(sub.trial_ends_at)
    created = _aware(getattr(org, "created_at", None)) or _utcnow()
    return created + timedelta(days=TRIAL_DAYS)


def _trial_still_active(sub: Optional[Subscription], now: datetime) -> bool:
    """Stripe / paid trial still within window (status must be trialing)."""
    if sub is None:
        return False
    if (sub.status or "").lower() != "trialing":
        return False
    ends = _aware(sub.trial_ends_at)
    if ends is None:
        return True
    return ends > now


def _paid_subscription_active(sub: Optional[Subscription], plan: str, now: datetime) -> bool:
    """Whether a paid plan currently has write/feature access."""
    if plan not in PAID_PLANS:
        return False
    if sub is None:
        # Local checkout / snapshot: trust plan if paid
        return True

    sub_status = (sub.status or "active").lower()
    if sub_status in {"canceled", "unpaid", "incomplete", "incomplete_expired", "expired"}:
        return False
    if sub_status == "trialing":
        return _trial_still_active(sub, now)
    return sub_status in {"active", "past_due"}


def resolve_entitlements(
    org: Organization,
    sub: Optional[Subscription],
) -> EntitlementSnapshot:
    """Compute feature access from plan + evaluation/subscription status."""
    now = _utcnow()
    plan = (org.plan or "free").lower()
    limits = get_plan_limits(plan)
    raw_status = ((sub.status if sub else None) or "active").lower()

    if plan == "free":
        ends = evaluation_ends_at(org, sub)
        evaluation_active = bool(ends and ends > now)
        evaluation_expired = not evaluation_active
        write_active = evaluation_active
        trial_active = evaluation_active
        trial_ends = ends
        status_out = "trialing" if evaluation_active else "expired"
    else:
        evaluation_active = False
        evaluation_expired = False
        write_active = _paid_subscription_active(sub, plan, now)
        trial_active = _trial_still_active(sub, now)
        trial_ends = _aware(sub.trial_ends_at) if sub else None
        if write_active:
            status_out = "trialing" if trial_active else (raw_status if sub else "active")
        else:
            status_out = "expired" if raw_status in {"expired", "canceled", "unpaid"} else raw_status

    read_only = not write_active

    # Upgrade Simulator = analysis only; requires active evaluation or paid access
    can_simulator = bool(limits.upgrade_simulator and write_active)
    # Pro+: AI advisor
    ai_enabled = bool(limits.ai_enabled and write_active)
    # Team/Enterprise: Migration Assistant code generation
    can_migration = bool(
        limits.ai_migration_assistant and plan in TEAM_PLANS and write_active
    )

    return EntitlementSnapshot(
        plan=plan,
        status=status_out,
        trial_active=trial_active,
        trial_ends_at=trial_ends,
        evaluation_active=evaluation_active,
        evaluation_expired=evaluation_expired,
        read_only=read_only,
        can_write=write_active,
        can_import_repositories=write_active,
        can_trigger_scans=write_active,
        can_sync_repositories=write_active,
        can_run_background_jobs=write_active,
        upgrade_simulator=can_simulator,
        ai_enabled=ai_enabled,
        ai_migration_assistant=can_migration,
        teams_enabled=bool(limits.teams_enabled and write_active),
        rbac=bool(limits.rbac and write_active),
        api_access=bool(limits.api_access and write_active),
        scheduled_scans=bool(limits.scheduled_scans and write_active),
        webhooks=bool(limits.webhooks and write_active),
        export_reports=bool(limits.export_reports and write_active),
        can_generate_ai_migration=can_migration,
        can_view_ai_migration_reports=True,
        monthly_scan_limit=limits.monthly_scan_limit,
        max_repositories=limits.max_repositories,
        max_users=limits.max_users,
    )


async def get_org_subscription(
    db: AsyncSession, org: Organization
) -> Optional[Subscription]:
    return (
        await db.execute(select(Subscription).where(Subscription.organization_id == org.id))
    ).scalar_one_or_none()


async def ensure_evaluation_subscription(
    db: AsyncSession, org: Organization
) -> Optional[Subscription]:
    """
    Ensure free-plan orgs have a trial_ends_at window.

    New orgs set this at creation. Existing free orgs without a window are
    backfilled from organization.created_at + TRIAL_DAYS.
    """
    if (org.plan or "free").lower() != "free":
        return await get_org_subscription(db, org)

    sub = await get_org_subscription(db, org)
    now = _utcnow()
    if sub is None:
        ends = evaluation_ends_at(org, None)
        sub = Subscription(
            organization_id=org.id,
            plan="free",
            status="trialing" if ends and ends > now else "expired",
            billing_interval="month",
            seat_count=1,
            trial_ends_at=ends,
        )
        db.add(sub)
        await db.flush()
        return sub

    if sub.trial_ends_at is None:
        ends = evaluation_ends_at(org, None)
        sub.trial_ends_at = ends
        if ends and ends > now:
            if (sub.status or "").lower() in {"active", "trialing", ""}:
                sub.status = "trialing"
        else:
            if (sub.status or "").lower() in {"active", "trialing"}:
                sub.status = "expired"
        await db.flush()
    return sub


async def get_entitlements(db: AsyncSession, org: Organization) -> EntitlementSnapshot:
    sub = await ensure_evaluation_subscription(db, org)
    return resolve_entitlements(org, sub)


def _expired_detail(
    entitlements: EntitlementSnapshot,
    *,
    feature: str,
    message: str,
) -> dict[str, Any]:
    code = "evaluation_expired" if entitlements.evaluation_expired else "subscription_required"
    return {
        "code": code,
        "feature": feature,
        "plan": entitlements.plan,
        "status": entitlements.status,
        "evaluation_expired": entitlements.evaluation_expired,
        "read_only": entitlements.read_only,
        "trial_ends_at": entitlements.trial_ends_at.isoformat()
        if entitlements.trial_ends_at
        else None,
        "message": message,
        "upgrade_url": "/billing?plan=starter",
        "required_plans": ["starter", "pro", "team", "enterprise"],
    }


async def require_write_access(
    db: AsyncSession,
    *,
    org: Organization,
    feature: str = "write",
) -> EntitlementSnapshot:
    """Block imports, scans, sync, and background jobs when evaluation/subscription is inactive."""
    entitlements = await get_entitlements(db, org)
    if entitlements.can_write:
        return entitlements

    if entitlements.evaluation_expired:
        message = (
            "Your 7-day evaluation has ended. Upgrade to Starter or higher to import "
            "repositories, run scans, sync, and use background jobs. Your existing data "
            "remains available."
        )
    else:
        message = (
            "An active subscription is required for this action. "
            "Upgrade to continue using Verspect."
        )
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail=_expired_detail(entitlements, feature=feature, message=message),
    )


async def count_scans_this_month(
    db: AsyncSession,
    *,
    org: Organization,
    owner_user_id: Optional[UUID] = None,
) -> int:
    """Count scans created this calendar month for the org (owner fallback)."""
    from app.models.repository import Repository
    from app.models.scan import Scan

    now = _utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    count = await db.scalar(
        select(func.count())
        .select_from(Scan)
        .join(Repository, Scan.repository_id == Repository.id)
        .where(
            Repository.organization_id == org.id,
            Repository.deleted_at.is_(None),
            Scan.created_at >= month_start,
        )
    )
    if count:
        return int(count)
    if owner_user_id is None:
        return 0
    fallback = await db.scalar(
        select(func.count())
        .select_from(Scan)
        .join(Repository, Scan.repository_id == Repository.id)
        .where(
            Repository.owner_id == owner_user_id,
            Repository.deleted_at.is_(None),
            Scan.created_at >= month_start,
        )
    )
    return int(fallback or 0)


async def require_upgrade_simulator(
    db: AsyncSession,
    *,
    org: Organization,
) -> EntitlementSnapshot:
    """Upgrade Simulator requires an active evaluation or paid subscription."""
    entitlements = await get_entitlements(db, org)
    if entitlements.upgrade_simulator:
        return entitlements

    if entitlements.evaluation_expired:
        message = (
            "Upgrade Simulator requires an active evaluation or paid plan. "
            "Your 7-day evaluation has ended — upgrade to continue analyzing upgrades. "
            "Previous simulation reports remain visible."
        )
    else:
        message = "Upgrade Simulator is unavailable on your current plan."
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail=_expired_detail(
            entitlements,
            feature=FEATURE_UPGRADE_SIMULATOR,
            message=message,
        ),
    )


async def require_ai_migration_assistant(
    db: AsyncSession,
    *,
    org: Organization,
) -> EntitlementSnapshot:
    """
    Enforce Team/Enterprise access for AI Migration Assistant.

    Evaluation, Starter, and Pro receive 403. Never starts AI migration work without this check.
    """
    entitlements = await get_entitlements(db, org)
    if entitlements.can_generate_ai_migration:
        return entitlements

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "premium_required",
            "feature": FEATURE_AI_MIGRATION,
            "plan": entitlements.plan,
            "message": "AI Migration Assistant requires a Team or Enterprise subscription.",
            "upgrade_url": "/billing?plan=team",
            "required_plans": ["team", "enterprise"],
        },
    )


async def require_ai_feature(db: AsyncSession, *, org: Organization) -> EntitlementSnapshot:
    """Gate general AI analysis (advisor refresh, summaries) — Pro+."""
    entitlements = await get_entitlements(db, org)
    if entitlements.ai_enabled:
        return entitlements
    try:
        require_feature(org.plan, feature=FEATURE_AI)
    except HTTPException:
        pass
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "premium_required",
            "feature": "ai",
            "plan": entitlements.plan,
            "message": "AI Upgrade Advisor requires a Pro subscription or higher.",
            "upgrade_url": "/billing?plan=pro",
        },
    )


def _month_key(now: Optional[datetime] = None) -> str:
    stamp = now or _utcnow()
    return f"{stamp.year:04d}-{stamp.month:02d}"


async def record_feature_usage(
    db: AsyncSession,
    *,
    organization_id: UUID,
    user_id: UUID,
    feature: str,
    repository_id: Optional[UUID] = None,
    dependency_id: Optional[UUID] = None,
    simulation_id: Optional[UUID] = None,
    tokens_used: Optional[int] = None,
    estimated_cost_usd: Optional[float] = None,
    execution_time_ms: Optional[int] = None,
    meta: Optional[dict[str, Any]] = None,
) -> FeatureUsageEvent:
    event = FeatureUsageEvent(
        organization_id=organization_id,
        user_id=user_id,
        feature=feature,
        repository_id=repository_id,
        dependency_id=dependency_id,
        simulation_id=simulation_id,
        month_key=_month_key(),
        tokens_used=tokens_used,
        estimated_cost_usd=estimated_cost_usd,
        execution_time_ms=execution_time_ms,
        extra_metadata=meta or {},
    )
    db.add(event)
    await db.flush()
    return event


def record_feature_usage_sync(
    session,
    *,
    organization_id: UUID,
    user_id: UUID,
    feature: str,
    repository_id: Optional[UUID] = None,
    dependency_id: Optional[UUID] = None,
    simulation_id: Optional[UUID] = None,
    tokens_used: Optional[int] = None,
    estimated_cost_usd: Optional[float] = None,
    execution_time_ms: Optional[int] = None,
    meta: Optional[dict[str, Any]] = None,
) -> FeatureUsageEvent:
    event = FeatureUsageEvent(
        organization_id=organization_id,
        user_id=user_id,
        feature=feature,
        repository_id=repository_id,
        dependency_id=dependency_id,
        simulation_id=simulation_id,
        month_key=_month_key(),
        tokens_used=tokens_used,
        estimated_cost_usd=estimated_cost_usd,
        execution_time_ms=execution_time_ms,
        extra_metadata=meta or {},
    )
    session.add(event)
    session.flush()
    return event


async def sum_migration_usage_month(
    db: AsyncSession, *, organization_id: UUID
) -> dict[str, Any]:
    """Aggregate Upgrade Simulator + AI Migration Assistant usage for the month."""
    now = _utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = (
        await db.execute(
            select(
                FeatureUsageEvent.feature,
                func.count(FeatureUsageEvent.id),
                func.coalesce(func.sum(FeatureUsageEvent.tokens_used), 0),
                func.coalesce(func.sum(FeatureUsageEvent.estimated_cost_usd), 0),
                func.coalesce(func.avg(FeatureUsageEvent.execution_time_ms), 0),
            )
            .where(
                FeatureUsageEvent.organization_id == organization_id,
                FeatureUsageEvent.created_at >= month_start,
                FeatureUsageEvent.feature.in_(
                    [FEATURE_AI_MIGRATION, "upgrade_simulator", "ai"]
                ),
            )
            .group_by(FeatureUsageEvent.feature)
        )
    ).all()

    requests = 0
    tokens = 0
    cost = 0.0
    avg_ms = 0
    for _feature, count, tok, c, avg in rows:
        requests += int(count or 0)
        tokens += int(tok or 0)
        cost += float(c or 0)
        if avg:
            avg_ms = int(avg)
    return {
        "requests": requests,
        "tokens": tokens,
        "estimated_cost_usd": cost,
        "avg_execution_time_ms": avg_ms,
    }
