"""Organization lifecycle helpers — personal org on signup, invites, roles."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.billing import Subscription
from app.models.organization import Organization, OrganizationInvitation, OrganizationMember
from app.models.user import User
from app.services.plans import TRIAL_DAYS, assert_seat_limit


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "org").lower()).strip("-")[:80] or "org"
    return base


async def ensure_personal_organization(db: AsyncSession, user: User) -> Organization:
    """Create a personal Free org for the user if missing."""
    result = await db.execute(
        select(Organization).where(
            Organization.owner_user_id == user.id,
            Organization.is_personal.is_(True),
            Organization.deleted_at.is_(None),
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        if not user.active_organization_id:
            user.active_organization_id = existing.id
        return existing

    slug = _slugify(user.github_login or user.email or "user")
    # Ensure unique slug
    taken = await db.execute(select(Organization.id).where(Organization.slug == slug))
    if taken.scalar_one_or_none():
        slug = f"{slug}-{str(user.id)[:8]}"

    from app.core.config import get_settings

    billing_provider = (get_settings().billing_provider or "stripe").strip().lower()
    org = Organization(
        name=f"{user.name or user.github_login}'s Workspace",
        slug=slug,
        owner_user_id=user.id,
        plan="free",
        is_personal=True,
        billing_provider=billing_provider,
    )
    db.add(org)
    await db.flush()

    db.add(
        OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="owner",
            joined_at=datetime.now(timezone.utc),
        )
    )
    now = datetime.now(timezone.utc)
    db.add(
        Subscription(
            organization_id=org.id,
            plan="free",
            status="trialing",
            billing_interval="month",
            seat_count=1,
            trial_ends_at=now + timedelta(days=TRIAL_DAYS),
            billing_provider=billing_provider,
        )
    )
    user.active_organization_id = org.id
    await db.flush()
    return org


def ensure_personal_organization_sync(db: Session, user: User) -> Organization:
    existing = db.execute(
        select(Organization).where(
            Organization.owner_user_id == user.id,
            Organization.is_personal.is_(True),
            Organization.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing:
        if not user.active_organization_id:
            user.active_organization_id = existing.id
        return existing

    slug = _slugify(user.github_login or user.email or "user")
    taken = db.execute(select(Organization.id).where(Organization.slug == slug)).scalar_one_or_none()
    if taken:
        slug = f"{slug}-{str(user.id)[:8]}"

    from app.core.config import get_settings

    billing_provider = (get_settings().billing_provider or "stripe").strip().lower()
    org = Organization(
        name=f"{user.name or user.github_login}'s Workspace",
        slug=slug,
        owner_user_id=user.id,
        plan="free",
        is_personal=True,
        billing_provider=billing_provider,
    )
    db.add(org)
    db.flush()
    db.add(
        OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="owner",
            joined_at=datetime.now(timezone.utc),
        )
    )
    now = datetime.now(timezone.utc)
    db.add(
        Subscription(
            organization_id=org.id,
            plan="free",
            status="trialing",
            billing_interval="month",
            seat_count=1,
            trial_ends_at=now + timedelta(days=TRIAL_DAYS),
            billing_provider=billing_provider,
        )
    )
    user.active_organization_id = org.id
    db.flush()
    return org


async def get_user_membership(
    db: AsyncSession, user_id: UUID, organization_id: UUID
) -> Optional[OrganizationMember]:
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == organization_id,
        )
    )
    return result.scalar_one_or_none()


async def get_active_organization(db: AsyncSession, user: User) -> Organization:
    """Return the user's active org only when they are a current member.

    Stale ``active_organization_id`` values (e.g. after removal) are cleared and
    the personal organization is used instead.
    """
    if user.active_organization_id:
        result = await db.execute(
            select(Organization)
            .join(
                OrganizationMember,
                OrganizationMember.organization_id == Organization.id,
            )
            .where(
                Organization.id == user.active_organization_id,
                Organization.deleted_at.is_(None),
                OrganizationMember.user_id == user.id,
            )
        )
        org = result.scalar_one_or_none()
        if org:
            return org
        # Membership gone or org deleted — revoke stale pointer immediately.
        user.active_organization_id = None
    return await ensure_personal_organization(db, user)


async def clear_active_organization_if_match(
    db: AsyncSession, *, user_id: UUID, organization_id: UUID
) -> None:
    """If the user's active org is ``organization_id``, clear it (access revoked)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is not None and user.active_organization_id == organization_id:
        user.active_organization_id = None


async def create_invitation(
    db: AsyncSession,
    *,
    org: Organization,
    email: str,
    role: str,
    invited_by: User,
) -> OrganizationInvitation:
    member_count = await db.scalar(
        select(func.count()).select_from(OrganizationMember).where(
            OrganizationMember.organization_id == org.id
        )
    )
    pending = await db.scalar(
        select(func.count()).select_from(OrganizationInvitation).where(
            OrganizationInvitation.organization_id == org.id,
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.revoked_at.is_(None),
        )
    )
    assert_seat_limit(org.plan, int(member_count or 0) + int(pending or 0), adding=1)

    token = secrets.token_urlsafe(32)
    invite = OrganizationInvitation(
        organization_id=org.id,
        email=email.lower().strip(),
        role=role if role in {"admin", "developer", "viewer"} else "developer",
        token=token,
        invited_by_id=invited_by.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    await db.flush()
    return invite
