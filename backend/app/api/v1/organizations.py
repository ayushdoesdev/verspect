"""Organization and team management APIs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps.auth import CurrentUser, DbSession
from app.core.config import get_settings
from app.models.billing import Subscription
from app.models.organization import Organization, OrganizationInvitation, OrganizationMember
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.organization import (
    InviteCreate,
    InvitationResponse,
    LicensePolicyResponse,
    LicensePolicyUpdate,
    MemberResponse,
    MemberRoleUpdate,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
    SwitchOrganizationRequest,
)
from app.services.organizations import (
    clear_active_organization_if_match,
    create_invitation,
    ensure_personal_organization,
    get_active_organization,
    get_user_membership,
    _slugify,
)
from app.services.plans import TRIAL_DAYS, assert_seat_limit, require_feature

router = APIRouter()


def _org_response(org: Organization, role: str | None = None) -> OrganizationResponse:
    from app.schemas.organization import LicensePolicyResponse
    from app.services.license_policy import public_license_policy

    policy = public_license_policy(org.settings if isinstance(org.settings, dict) else None)
    return OrganizationResponse(
        id=org.id,
        created_at=org.created_at,
        updated_at=org.updated_at,
        name=org.name,
        slug=org.slug,
        description=org.description,
        logo_url=org.logo_url,
        website=org.website,
        plan=org.plan,
        is_personal=org.is_personal,
        owner_user_id=org.owner_user_id,
        role=role,
        license_policy=LicensePolicyResponse(**policy),
    )


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(db: DbSession, current_user: CurrentUser) -> list[OrganizationResponse]:
    await ensure_personal_organization(db, current_user)
    result = await db.execute(
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            OrganizationMember.user_id == current_user.id,
            Organization.deleted_at.is_(None),
        )
        .order_by(Organization.is_personal.desc(), Organization.name)
    )
    rows = result.all()
    await db.commit()
    return [_org_response(org, role) for org, role in rows]


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    db: DbSession,
    current_user: CurrentUser,
    body: OrganizationCreate,
) -> OrganizationResponse:
    active = await get_active_organization(db, current_user)
    from app.services.entitlements import get_entitlements

    ents = await get_entitlements(db, active)
    if not ents.teams_enabled:
        require_feature(active.plan, feature="teams")

    # Creating an org only requires Teams on the *current* workspace.
    # The new org must never inherit a paid plan — paid status comes only from checkout/webhooks.
    slug = body.slug or _slugify(body.name)
    taken = await db.execute(select(Organization.id).where(Organization.slug == slug))
    if taken.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Organization slug already taken")

    billing_provider = (get_settings().billing_provider or "stripe").strip().lower()
    now = datetime.now(timezone.utc)
    org = Organization(
        name=body.name,
        slug=slug,
        owner_user_id=current_user.id,
        plan="free",
        is_personal=False,
        billing_provider=billing_provider,
    )
    db.add(org)
    await db.flush()
    db.add(
        OrganizationMember(
            organization_id=org.id,
            user_id=current_user.id,
            role="owner",
            joined_at=now,
        )
    )
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
    current_user.active_organization_id = org.id
    await db.commit()
    await db.refresh(org)
    return _org_response(org, "owner")


@router.get("/current", response_model=OrganizationResponse)
async def current_organization(db: DbSession, current_user: CurrentUser) -> OrganizationResponse:
    org = await get_active_organization(db, current_user)
    membership = await get_user_membership(db, current_user.id, org.id)
    await db.commit()
    return _org_response(org, membership.role if membership else None)


@router.post("/switch", response_model=OrganizationResponse)
async def switch_organization(
    db: DbSession,
    current_user: CurrentUser,
    body: SwitchOrganizationRequest,
) -> OrganizationResponse:
    membership = await get_user_membership(db, current_user.id, body.organization_id)
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    org = (
        await db.execute(
            select(Organization).where(
                Organization.id == body.organization_id,
                Organization.deleted_at.is_(None),
            )
        )
    ).scalar_one()
    current_user.active_organization_id = org.id
    await db.commit()
    return _org_response(org, membership.role)


@router.patch("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    db: DbSession,
    current_user: CurrentUser,
    organization_id: UUID,
    body: OrganizationUpdate,
) -> OrganizationResponse:
    membership = await get_user_membership(db, current_user.id, organization_id)
    if membership is None or membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    org = (
        await db.execute(select(Organization).where(Organization.id == organization_id))
    ).scalar_one()
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    await db.commit()
    await db.refresh(org)
    return _org_response(org, membership.role)


@router.get(
    "/{organization_id}/license-policy",
    response_model=LicensePolicyResponse,
)
async def get_license_policy(
    db: DbSession,
    current_user: CurrentUser,
    organization_id: UUID,
) -> LicensePolicyResponse:
    membership = await get_user_membership(db, current_user.id, organization_id)
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member")
    org = (
        await db.execute(select(Organization).where(Organization.id == organization_id))
    ).scalar_one()
    from app.services.license_policy import public_license_policy

    return LicensePolicyResponse(
        **public_license_policy(org.settings if isinstance(org.settings, dict) else None)
    )


@router.put(
    "/{organization_id}/license-policy",
    response_model=LicensePolicyResponse,
)
async def update_license_policy(
    db: DbSession,
    current_user: CurrentUser,
    organization_id: UUID,
    body: LicensePolicyUpdate,
) -> LicensePolicyResponse:
    """Set organization license reject/warn lists. Applied on the next repository scan."""
    membership = await get_user_membership(db, current_user.id, organization_id)
    if membership is None or membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    org = (
        await db.execute(select(Organization).where(Organization.id == organization_id))
    ).scalar_one()
    from app.services.license_policy import normalize_license_list, public_license_policy

    settings = dict(org.settings or {})
    policy = dict(settings.get("license_policy") or {})
    data = body.model_dump(exclude_unset=True)
    if "reject" in data:
        policy["reject"] = normalize_license_list(data["reject"])
    if "warn" in data:
        policy["warn"] = normalize_license_list(data["warn"])
    settings["license_policy"] = policy
    org.settings = settings
    await db.commit()
    await db.refresh(org)
    return LicensePolicyResponse(
        **public_license_policy(org.settings if isinstance(org.settings, dict) else None)
    )


@router.get("/{organization_id}/members", response_model=list[MemberResponse])
async def list_members(
    db: DbSession,
    current_user: CurrentUser,
    organization_id: UUID,
) -> list[MemberResponse]:
    membership = await get_user_membership(db, current_user.id, organization_id)
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member")
    result = await db.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == organization_id)
    )
    out = []
    for m, u in result.all():
        out.append(
            MemberResponse(
                id=m.id,
                user_id=u.id,
                role=m.role,
                email=u.email,
                name=u.name,
                github_login=u.github_login,
                avatar_url=u.avatar_url,
                joined_at=m.joined_at,
            )
        )
    return out


@router.patch("/{organization_id}/members/{user_id}", response_model=MemberResponse)
async def update_member_role(
    db: DbSession,
    current_user: CurrentUser,
    organization_id: UUID,
    user_id: UUID,
    body: MemberRoleUpdate,
) -> MemberResponse:
    actor = await get_user_membership(db, current_user.id, organization_id)
    if actor is None or actor.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if body.role not in {"admin", "developer", "viewer", "owner"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    target = await get_user_membership(db, user_id, organization_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if target.role == "owner" and actor.role != "owner":
        raise HTTPException(status_code=403, detail="Only owner can change owner role")
    target.role = body.role
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    await db.commit()
    return MemberResponse(
        id=target.id,
        user_id=user.id,
        role=target.role,
        email=user.email,
        name=user.name,
        github_login=user.github_login,
        avatar_url=user.avatar_url,
        joined_at=target.joined_at,
    )


@router.delete("/{organization_id}/members/{user_id}", response_model=MessageResponse)
async def remove_member(
    db: DbSession,
    current_user: CurrentUser,
    organization_id: UUID,
    user_id: UUID,
) -> MessageResponse:
    actor = await get_user_membership(db, current_user.id, organization_id)
    if actor is None or actor.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    target = await get_user_membership(db, user_id, organization_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if target.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove the owner")
    await db.delete(target)
    # Immediately revoke workspace context for the removed member.
    await clear_active_organization_if_match(
        db, user_id=user_id, organization_id=organization_id
    )
    await db.commit()
    return MessageResponse(message="Member removed")


@router.post(
    "/{organization_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    db: DbSession,
    current_user: CurrentUser,
    organization_id: UUID,
    body: InviteCreate,
) -> InvitationResponse:
    actor = await get_user_membership(db, current_user.id, organization_id)
    if actor is None or actor.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    org = (await db.execute(select(Organization).where(Organization.id == organization_id))).scalar_one()
    from app.services.entitlements import get_entitlements

    ents = await get_entitlements(db, org)
    if not ents.teams_enabled:
        require_feature(org.plan, feature="teams")
    invite = await create_invitation(
        db, org=org, email=body.email, role=body.role, invited_by=current_user
    )
    await db.commit()
    await db.refresh(invite)
    return InvitationResponse(
        id=invite.id,
        created_at=invite.created_at,
        updated_at=invite.updated_at,
        email=invite.email,
        role=invite.role,
        expires_at=invite.expires_at,
        accepted_at=invite.accepted_at,
        token=invite.token,
    )


@router.get("/{organization_id}/invitations", response_model=list[InvitationResponse])
async def list_invitations(
    db: DbSession,
    current_user: CurrentUser,
    organization_id: UUID,
) -> list[InvitationResponse]:
    actor = await get_user_membership(db, current_user.id, organization_id)
    if actor is None or actor.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    result = await db.execute(
        select(OrganizationInvitation).where(
            OrganizationInvitation.organization_id == organization_id,
            OrganizationInvitation.revoked_at.is_(None),
        )
    )
    return [
        InvitationResponse(
            id=i.id,
            created_at=i.created_at,
            updated_at=i.updated_at,
            email=i.email,
            role=i.role,
            expires_at=i.expires_at,
            accepted_at=i.accepted_at,
        )
        for i in result.scalars().all()
    ]


@router.post("/invitations/{token}/accept", response_model=OrganizationResponse)
async def accept_invitation(
    db: DbSession,
    current_user: CurrentUser,
    token: str,
) -> OrganizationResponse:
    invite = (
        await db.execute(
            select(OrganizationInvitation).where(
                OrganizationInvitation.token == token,
                OrganizationInvitation.revoked_at.is_(None),
                OrganizationInvitation.accepted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if invite is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invitation expired")
    org = (await db.execute(select(Organization).where(Organization.id == invite.organization_id))).scalar_one()
    count = await db.scalar(
        select(func.count()).select_from(OrganizationMember).where(
            OrganizationMember.organization_id == org.id
        )
    )
    assert_seat_limit(org.plan, int(count or 0), adding=1)
    existing = await get_user_membership(db, current_user.id, org.id)
    if existing is None:
        db.add(
            OrganizationMember(
                organization_id=org.id,
                user_id=current_user.id,
                role=invite.role,
                invited_by_id=invite.invited_by_id,
                joined_at=datetime.now(timezone.utc),
            )
        )
    invite.accepted_at = datetime.now(timezone.utc)
    current_user.active_organization_id = org.id
    await db.commit()
    return _org_response(org, invite.role)
