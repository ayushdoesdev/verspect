"""Soft limit enforcement on plan reductions — never delete customer data.

When a plan shrinks (downgrade or cancel → Evaluation):
  • Excess active repositories are auto-archived (history retained)
  • Members stay; new invites blocked by seat limits
  • Organizations stay; creating new ones stays Team-gated
  • Scheduled scans / API / webhooks / AI Migration stop via entitlements
  • Historical reports, scans, AI results remain readable
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.organization import Organization, OrganizationMember
from app.models.repository import Repository
from app.models.user import User
from app.services.plans import get_plan_limits
from app.services import repository_lifecycle as lifecycle

logger = get_logger(__name__)


async def count_active_repositories(
    db: AsyncSession,
    *,
    organization_id: Optional[UUID] = None,
    owner_id: Optional[UUID] = None,
) -> int:
    """Active = not deleted and not archived (archived do not consume plan slots)."""
    q = select(func.count()).select_from(Repository).where(
        Repository.deleted_at.is_(None),
        Repository.is_archived.is_(False),
    )
    if organization_id is not None:
        q = q.where(Repository.organization_id == organization_id)
    elif owner_id is not None:
        q = q.where(Repository.owner_id == owner_id)
    return int(await db.scalar(q) or 0)


async def count_organization_members(db: AsyncSession, organization_id: UUID) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(OrganizationMember)
            .where(OrganizationMember.organization_id == organization_id)
        )
        or 0
    )


async def enforce_repository_soft_limit(
    db: AsyncSession,
    org: Organization,
    *,
    actor: Optional[User] = None,
) -> list[UUID]:
    """Archive oldest excess active repos so active count ≤ plan max.

    Never deletes repositories. Returns archived repository ids.
    """
    limits = get_plan_limits(org.plan)
    max_repos = limits.max_repositories
    if max_repos is None:
        return []

    active = (
        await db.execute(
            select(Repository)
            .where(
                Repository.organization_id == org.id,
                Repository.deleted_at.is_(None),
                Repository.is_archived.is_(False),
            )
            .order_by(Repository.created_at.asc(), Repository.id.asc())
        )
    ).scalars().all()

    # Fallback when org_id not set on older rows — use owner
    if not active and org.owner_user_id:
        active = (
            await db.execute(
                select(Repository)
                .where(
                    Repository.owner_id == org.owner_user_id,
                    Repository.deleted_at.is_(None),
                    Repository.is_archived.is_(False),
                )
                .order_by(Repository.created_at.asc(), Repository.id.asc())
            )
        ).scalars().all()

    if len(active) <= max_repos:
        return []

    # Keep the most recently created / freshest slots; archive the oldest excess.
    keep = set(r.id for r in active[-max_repos:])
    to_archive = [r for r in active if r.id not in keep]
    archived_ids: list[UUID] = []

    for repo in to_archive:
        if repo.is_archived:
            continue
        await lifecycle.archive_repository(
            db,
            repo,
            actor=actor,
            plan=org.plan,
            reason="plan_limit",
        )
        archived_ids.append(repo.id)
        logger.info(
            "soft_limit_archived_repository",
            repository_id=str(repo.id),
            organization_id=str(org.id),
            plan=org.plan,
        )

    await db.flush()
    return archived_ids


async def enforce_plan_soft_limits(
    db: AsyncSession,
    org: Organization,
    *,
    actor: Optional[User] = None,
) -> dict:
    """Apply all soft reductions for the org's current plan. Data-safe."""
    archived = await enforce_repository_soft_limit(db, org, actor=actor)
    members = await count_organization_members(db, org.id)
    limits = get_plan_limits(org.plan)
    return {
        "archived_repository_ids": [str(i) for i in archived],
        "active_repositories": await count_active_repositories(
            db, organization_id=org.id
        ),
        "repositories_limit": limits.max_repositories,
        "members": members,
        "members_limit": limits.max_users,
        # Feature gates (API, webhooks, scheduled scans, AI migration) are
        # enforced live via entitlements — no destructive cleanup.
    }
