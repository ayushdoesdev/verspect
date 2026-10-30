"""Platform admin dashboard APIs — is_admin only."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import cast, Date, func, or_, select

from app.api.deps.auth import DbSession, PlatformAdmin
from app.core.enums import ScanStatus, ScanType, SimulationStatus
from app.core.pagination import PaginatedResponse
from app.models.feedback import FeedbackSubmission
from app.models.organization import Organization, OrganizationMember
from app.models.repository import Repository
from app.models.scan import Scan
from app.models.upgrade_simulation import UpgradeSimulation
from app.models.user import User
from app.schemas.contact import ContactResponse
from app.schemas.feedback import ALLOWED_STATUSES, FeedbackResponse, FeedbackStatusUpdate
from app.services.plans import PLANS

router = APIRouter()

ACTIVE_SCAN_STATUSES = {
    ScanStatus.PENDING.value,
    ScanStatus.QUEUED.value,
    ScanStatus.RUNNING.value,
    ScanStatus.CLONING.value,
    ScanStatus.CLASSIFYING.value,
    ScanStatus.SCANNING_MANIFESTS.value,
    ScanStatus.PARSING_AST.value,
    ScanStatus.CHECKING_VERSIONS.value,
    ScanStatus.CHECKING_VULNERABILITIES.value,
    ScanStatus.CHECKING_LICENSES.value,
    ScanStatus.SCORING_HEALTH.value,
    ScanStatus.ANALYZING_AI.value,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _day_start(now: Optional[datetime] = None) -> datetime:
    n = now or _utcnow()
    return n.replace(hour=0, minute=0, second=0, microsecond=0)


class AdminOverview(BaseModel):
    total_users: int
    verified_users: int
    organizations: int
    repositories: int
    repository_scans: int
    active_scans: int
    ai_advisor_jobs: int
    upgrade_simulations: int
    daily_signups: int
    daily_imports: int
    daily_scans: int
    failed_jobs: int
    workers: str
    redis: str
    database: str


class AdminAnalytics(BaseModel):
    daily_users: list[dict[str, Any]]
    daily_scans: list[dict[str, Any]]
    daily_simulations: list[dict[str, Any]]
    ai_advisor_usage: list[dict[str, Any]]
    failed_jobs: list[dict[str, Any]]
    average_scan_duration_seconds: Optional[float]
    average_simulation_duration_seconds: Optional[float]


class AdminUserRow(BaseModel):
    id: UUID
    name: Optional[str]
    email: str
    plan: str
    verified: bool
    github_connected: bool
    repositories: int
    created_at: datetime
    last_login_at: Optional[datetime]
    status: str
    is_admin: bool


class AdminOrgRow(BaseModel):
    id: UUID
    name: str
    owner_email: Optional[str]
    plan: str
    members: int
    repository_count: int
    created_at: datetime


class AdminRepoRow(BaseModel):
    id: UUID
    full_name: str
    owner_email: Optional[str]
    health_score: Optional[float]
    dependency_count: int
    last_scan_at: Optional[datetime]
    sync_status: str
    is_archived: bool


@router.get("/overview", response_model=AdminOverview)
async def admin_overview(_admin: PlatformAdmin, db: DbSession) -> AdminOverview:
    start = _day_start()
    total_users = (
        await db.execute(select(func.count()).select_from(User).where(User.deleted_at.is_(None)))
    ).scalar_one()
    verified_users = (
        await db.execute(
            select(func.count())
            .select_from(User)
            .where(User.deleted_at.is_(None), User.email_verified.is_(True))
        )
    ).scalar_one()
    organizations = (
        await db.execute(
            select(func.count())
            .select_from(Organization)
            .where(Organization.deleted_at.is_(None))
        )
    ).scalar_one()
    repositories = (
        await db.execute(
            select(func.count()).select_from(Repository).where(Repository.deleted_at.is_(None))
        )
    ).scalar_one()
    active_scans = (
        await db.execute(
            select(func.count())
            .select_from(Scan)
            .where(Scan.status.in_(ACTIVE_SCAN_STATUSES))
        )
    ).scalar_one()
    ai_advisor_jobs = (
        await db.execute(
            select(func.count())
            .select_from(Scan)
            .where(
                Scan.scan_type == ScanType.AI_ADVISOR.value,
                Scan.status.in_(ACTIVE_SCAN_STATUSES),
            )
        )
    ).scalar_one()
    upgrade_simulations = (
        await db.execute(
            select(func.count())
            .select_from(UpgradeSimulation)
            .where(
                UpgradeSimulation.status.notin_(
                    {
                        SimulationStatus.COMPLETED.value,
                        SimulationStatus.FAILED.value,
                        SimulationStatus.CANCELLED.value,
                    }
                )
            )
        )
    ).scalar_one()
    daily_signups = (
        await db.execute(
            select(func.count())
            .select_from(User)
            .where(User.deleted_at.is_(None), User.created_at >= start)
        )
    ).scalar_one()
    daily_imports = (
        await db.execute(
            select(func.count())
            .select_from(Repository)
            .where(Repository.deleted_at.is_(None), Repository.created_at >= start)
        )
    ).scalar_one()
    daily_scans = (
        await db.execute(
            select(func.count()).select_from(Scan).where(Scan.created_at >= start)
        )
    ).scalar_one()
    failed_jobs = (
        await db.execute(
            select(func.count())
            .select_from(Scan)
            .where(Scan.status == ScanStatus.FAILED.value, Scan.completed_at >= start)
        )
    ).scalar_one()
    failed_sims = (
        await db.execute(
            select(func.count())
            .select_from(UpgradeSimulation)
            .where(
                UpgradeSimulation.status == SimulationStatus.FAILED.value,
                UpgradeSimulation.completed_at >= start,
            )
        )
    ).scalar_one()
    repository_scans = (
        await db.execute(
            select(func.count())
            .select_from(Scan)
            .where(Scan.scan_type != ScanType.AI_ADVISOR.value)
        )
    ).scalar_one()

    workers = "offline"
    redis = "unknown"
    database = "ok"
    try:
        from app.services.job_health import get_worker_health

        wh = get_worker_health(detailed=False, use_cache=True)
        workers = "online" if wh.online else "offline"
        redis = "ok" if wh.online or wh.queue_depths is not None else "degraded"
        # Queue depth probe uses Redis; empty dict can mean Redis reachable but empty.
        if wh.queue_depths is not None:
            redis = "ok"
    except Exception:  # noqa: BLE001
        workers = "unknown"
        redis = "unknown"
    try:
        await db.execute(select(func.now()))
    except Exception:  # noqa: BLE001
        database = "error"

    return AdminOverview(
        total_users=int(total_users or 0),
        verified_users=int(verified_users or 0),
        organizations=int(organizations or 0),
        repositories=int(repositories or 0),
        repository_scans=int(repository_scans or 0),
        active_scans=int(active_scans or 0),
        ai_advisor_jobs=int(ai_advisor_jobs or 0),
        upgrade_simulations=int(upgrade_simulations or 0),
        daily_signups=int(daily_signups or 0),
        daily_imports=int(daily_imports or 0),
        daily_scans=int(daily_scans or 0),
        failed_jobs=int(failed_jobs or 0) + int(failed_sims or 0),
        workers=workers,
        redis=redis,
        database=database,
    )


@router.get("/analytics", response_model=AdminAnalytics)
async def admin_analytics(
    _admin: PlatformAdmin,
    db: DbSession,
    days: int = Query(14, ge=1, le=90),
) -> AdminAnalytics:
    start = _day_start() - timedelta(days=days - 1)

    async def _daily_counts(model, ts_col, *, extra=None):
        q = (
            select(cast(ts_col, Date).label("day"), func.count().label("count"))
            .where(ts_col >= start)
        )
        if extra is not None:
            q = q.where(extra)
        q = q.group_by(cast(ts_col, Date)).order_by(cast(ts_col, Date))
        rows = (await db.execute(q)).all()
        return [{"date": str(r.day), "count": int(r.count)} for r in rows]

    daily_users = await _daily_counts(User, User.created_at, extra=User.deleted_at.is_(None))
    daily_scans = await _daily_counts(Scan, Scan.created_at)
    daily_simulations = await _daily_counts(UpgradeSimulation, UpgradeSimulation.created_at)
    ai_advisor_usage = await _daily_counts(
        Scan,
        Scan.created_at,
        extra=Scan.scan_type == ScanType.AI_ADVISOR.value,
    )
    failed_jobs = await _daily_counts(
        Scan,
        Scan.completed_at,
        extra=Scan.status == ScanStatus.FAILED.value,
    )

    avg_duration = (
        await db.execute(
            select(func.avg(Scan.duration_seconds)).where(
                Scan.status == ScanStatus.COMPLETED.value,
                Scan.duration_seconds.is_not(None),
                Scan.completed_at >= start,
                Scan.scan_type != ScanType.AI_ADVISOR.value,
            )
        )
    ).scalar_one()

    avg_sim = (
        await db.execute(
            select(func.avg(UpgradeSimulation.duration_seconds)).where(
                UpgradeSimulation.status == SimulationStatus.COMPLETED.value,
                UpgradeSimulation.duration_seconds.is_not(None),
                UpgradeSimulation.completed_at >= start,
            )
        )
    ).scalar_one()

    return AdminAnalytics(
        daily_users=daily_users,
        daily_scans=daily_scans,
        daily_simulations=daily_simulations,
        ai_advisor_usage=ai_advisor_usage,
        failed_jobs=failed_jobs,
        average_scan_duration_seconds=(
            round(float(avg_duration), 1) if avg_duration is not None else None
        ),
        average_simulation_duration_seconds=(
            round(float(avg_sim), 1) if avg_sim is not None else None
        ),
    )


@router.get("/users", response_model=PaginatedResponse[AdminUserRow])
async def admin_list_users(
    _admin: PlatformAdmin,
    db: DbSession,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> PaginatedResponse[AdminUserRow]:
    filters = [User.deleted_at.is_(None)]
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(User.email.ilike(like), User.name.ilike(like)))

    total = (
        await db.execute(select(func.count()).select_from(User).where(*filters))
    ).scalar_one()
    rows = (
        await db.execute(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    items: list[AdminUserRow] = []
    for u in rows:
        plan = "free"
        if u.active_organization_id:
            org = await db.get(Organization, u.active_organization_id)
            if org is not None:
                plan = org.plan or "free"
        display = PLANS.get(plan).display_name if plan in PLANS else plan
        repo_count = (
            await db.execute(
                select(func.count())
                .select_from(Repository)
                .where(
                    Repository.owner_id == u.id,
                    Repository.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        items.append(
            AdminUserRow(
                id=u.id,
                name=u.name,
                email=u.email or "",
                plan=display,
                verified=bool(u.email_verified),
                github_connected=bool(u.github_id),
                repositories=int(repo_count or 0),
                created_at=u.created_at,
                last_login_at=u.last_login_at,
                status="active" if u.is_active else "inactive",
                is_admin=bool(u.is_admin),
            )
        )
    return PaginatedResponse.create(
        items=items,
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )


@router.get("/organizations", response_model=PaginatedResponse[AdminOrgRow])
async def admin_list_organizations(
    _admin: PlatformAdmin,
    db: DbSession,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> PaginatedResponse[AdminOrgRow]:
    filters = [Organization.deleted_at.is_(None)]
    if q:
        filters.append(Organization.name.ilike(f"%{q.strip()}%"))

    total = (
        await db.execute(select(func.count()).select_from(Organization).where(*filters))
    ).scalar_one()
    orgs = (
        await db.execute(
            select(Organization)
            .where(*filters)
            .order_by(Organization.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    items: list[AdminOrgRow] = []
    for org in orgs:
        owner = await db.get(User, org.owner_user_id)
        owner_email = owner.email if owner else None
        members = (
            await db.execute(
                select(func.count())
                .select_from(OrganizationMember)
                .where(OrganizationMember.organization_id == org.id)
            )
        ).scalar_one()
        repos = (
            await db.execute(
                select(func.count())
                .select_from(Repository)
                .where(
                    Repository.organization_id == org.id,
                    Repository.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        plan = org.plan or "free"
        items.append(
            AdminOrgRow(
                id=org.id,
                name=org.name,
                owner_email=owner_email,
                plan=PLANS.get(plan).display_name if plan in PLANS else plan,
                members=int(members or 0),
                repository_count=int(repos or 0),
                created_at=org.created_at,
            )
        )
    return PaginatedResponse.create(
        items=items,
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )


@router.get("/repositories", response_model=PaginatedResponse[AdminRepoRow])
async def admin_list_repositories(
    _admin: PlatformAdmin,
    db: DbSession,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> PaginatedResponse[AdminRepoRow]:
    filters = [Repository.deleted_at.is_(None)]
    if q:
        filters.append(Repository.full_name.ilike(f"%{q.strip()}%"))

    total = (
        await db.execute(select(func.count()).select_from(Repository).where(*filters))
    ).scalar_one()
    repos = (
        await db.execute(
            select(Repository)
            .where(*filters)
            .order_by(Repository.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    items: list[AdminRepoRow] = []
    for r in repos:
        owner = await db.get(User, r.owner_id)
        items.append(
            AdminRepoRow(
                id=r.id,
                full_name=r.full_name,
                owner_email=owner.email if owner else None,
                health_score=r.health_score,
                dependency_count=int(r.dependency_count or 0),
                last_scan_at=r.last_synced_at,
                sync_status=r.sync_status or "unknown",
                is_archived=bool(r.is_archived),
            )
        )
    return PaginatedResponse.create(
        items=items,
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )


@router.get("/feedback", response_model=PaginatedResponse[FeedbackResponse])
async def admin_list_feedback(
    _admin: PlatformAdmin,
    db: DbSession,
    q: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> PaginatedResponse[FeedbackResponse]:
    filters = []
    if status_filter:
        if status_filter not in ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        filters.append(FeedbackSubmission.status == status_filter)
    if category:
        filters.append(FeedbackSubmission.category == category)
    if q:
        like = f"%{q.strip()}%"
        filters.append(
            or_(
                FeedbackSubmission.title.ilike(like),
                FeedbackSubmission.description.ilike(like),
                FeedbackSubmission.email.ilike(like),
            )
        )

    count_q = select(func.count()).select_from(FeedbackSubmission)
    list_q = select(FeedbackSubmission)
    if filters:
        count_q = count_q.where(*filters)
        list_q = list_q.where(*filters)

    total = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(
            list_q.order_by(FeedbackSubmission.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return PaginatedResponse.create(
        items=[FeedbackResponse.from_row(r) for r in rows],
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )


@router.get("/feedback/{feedback_id}", response_model=FeedbackResponse)
async def admin_get_feedback(
    feedback_id: UUID,
    _admin: PlatformAdmin,
    db: DbSession,
) -> FeedbackResponse:
    row = await db.get(FeedbackSubmission, feedback_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return FeedbackResponse.from_row(row)


@router.get("/feedback/{feedback_id}/screenshot")
async def admin_get_feedback_screenshot(
    feedback_id: UUID,
    _admin: PlatformAdmin,
    db: DbSession,
) -> FileResponse:
    row = await db.get(FeedbackSubmission, feedback_id)
    if row is None or not row.screenshot_path:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    path = Path(row.screenshot_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Screenshot file missing")
    return FileResponse(path)


@router.patch("/feedback/{feedback_id}", response_model=FeedbackResponse)
async def admin_update_feedback_status(
    feedback_id: UUID,
    body: FeedbackStatusUpdate,
    _admin: PlatformAdmin,
    db: DbSession,
) -> FeedbackResponse:
    row = await db.get(FeedbackSubmission, feedback_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    row.status = body.status
    await db.commit()
    await db.refresh(row)
    return FeedbackResponse.from_row(row)


@router.get("/contact-requests", response_model=PaginatedResponse[ContactResponse])
async def admin_list_contact_requests(
    _admin: PlatformAdmin,
    db: DbSession,
    q: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    from app.models.contact_request import ContactRequest

    filters = []
    if status_filter:
        filters.append(ContactRequest.status == status_filter)
    if q:
        like = f"%{q.strip()}%"
        filters.append(
            or_(
                ContactRequest.name.ilike(like),
                ContactRequest.email.ilike(like),
                ContactRequest.company.ilike(like),
                ContactRequest.message.ilike(like),
            )
        )
    count_q = select(func.count()).select_from(ContactRequest)
    list_q = select(ContactRequest)
    if filters:
        count_q = count_q.where(*filters)
        list_q = list_q.where(*filters)
    total = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(
            list_q.order_by(ContactRequest.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return PaginatedResponse.create(
        items=[ContactResponse.model_validate(r) for r in rows],
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )
