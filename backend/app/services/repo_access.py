"""Organization-scoped repository access (tenant isolation)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import OrganizationMember
from app.models.repository import Repository
from app.models.user import User
from app.services.organizations import get_active_organization, get_user_membership

WRITE_ROLES = frozenset({"owner", "admin", "developer"})


async def get_org_repository(
    db: AsyncSession,
    user: User,
    repository_id: UUID,
    *,
    write: bool = False,
) -> Repository:
    """Return a repository in the caller's active organization.

    Viewers can read. Write actions (sync, archive, delete, publish PR) require
    owner/admin/developer. Cross-organization IDs return 404 — never 403 leak.
    """
    org = await get_active_organization(db, user)
    membership = await get_user_membership(db, user.id, org.id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    result = await db.execute(
        select(Repository).where(
            Repository.id == repository_id,
            Repository.organization_id == org.id,
            Repository.deleted_at.is_(None),
        )
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if write and membership.role not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role cannot modify repositories in this organization.",
        )
    return repo


async def require_org_membership(
    db: AsyncSession,
    user: User,
    organization_id: UUID,
) -> OrganizationMember:
    membership = await get_user_membership(db, user.id, organization_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    return membership
