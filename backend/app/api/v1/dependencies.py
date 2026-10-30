"""Dependency list and detail endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps.auth import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.enums import SimulationStatus
from app.core.logging import get_logger
from app.core.pagination import PaginatedResponse
from app.models.dependency import Dependency
from app.models.repository import Repository
from app.models.upgrade_simulation import UpgradeSimulation
from app.services.job_health import (
    as_aware,
    classify_job,
    close_stage_timings,
    get_worker_health,
)
from app.services.job_health import utcnow as job_utcnow
from app.schemas.dependency import (
    AlternativeLibraryResponse,
    CVEResponse,
    DependencyDetailResponse,
    DependencyResponse,
    LibraryUsageResponse,
    MigrationReportResponse,
    ReleaseResponse,
    apply_osv_status,
)
from app.schemas.upgrade_simulation import (
    SimulateUpgradeRequest,
    UpgradeSimulationListItem,
    UpgradeSimulationResponse,
    enrich_simulation_response,
)

router = APIRouter()
logger = get_logger(__name__)

PENDING_SIMULATION_STATUSES = {
    SimulationStatus.PENDING.value,
    SimulationStatus.QUEUED.value,
}

RUNNING_SIMULATION_STATUSES = {
    SimulationStatus.COLLECTING_SOURCES.value,
    SimulationStatus.ANALYZING_IMPACT.value,
    SimulationStatus.GENERATING_PLAN.value,
    SimulationStatus.SCORING.value,
}

TERMINAL_SIMULATION_STATUSES = {
    SimulationStatus.COMPLETED.value,
    SimulationStatus.FAILED.value,
    SimulationStatus.CANCELLED.value,
}

ACTIVE_SIMULATION_STATUSES = PENDING_SIMULATION_STATUSES | RUNNING_SIMULATION_STATUSES


async def _reconcile_simulation(db: DbSession, sim: UpgradeSimulation) -> UpgradeSimulation:
    """Fail simulations whose worker never picked up, timed out, or went silent."""
    if sim.status in TERMINAL_SIMULATION_STATUSES:
        return sim

    settings = get_settings()
    verdict = classify_job(
        status=sim.status,
        terminal_statuses=TERMINAL_SIMULATION_STATUSES,
        pending_statuses=PENDING_SIMULATION_STATUSES,
        queued_at=sim.queued_at or sim.created_at,
        started_at=sim.started_at,
        last_heartbeat_at=sim.last_heartbeat_at,
        pickup_timeout_seconds=settings.simulation_pickup_timeout_seconds,
        running_timeout_minutes=settings.simulation_running_timeout_minutes,
        worker_online=get_worker_health().online,
    )
    if not verdict.is_unhealthy:
        return sim

    now = job_utcnow()
    sim.status = SimulationStatus.FAILED.value
    sim.current_stage = "failed"
    sim.error_message = verdict.message or "Simulation did not complete."
    sim.completed_at = now
    sim.stage_timings = close_stage_timings(sim.stage_timings, now=now)
    started = as_aware(sim.started_at)
    if started and sim.duration_seconds is None:
        sim.duration_seconds = (now - started).total_seconds()
    if sim.celery_task_id:
        try:
            from app.core.celery_app import celery_app

            celery_app.control.revoke(sim.celery_task_id, terminate=True)
        except Exception:  # noqa: BLE001
            pass
    await db.commit()
    await db.refresh(sim)
    logger.warning(
        "simulation_reaped",
        simulation_id=str(sim.id),
        reason=sim.error_message,
        worker=sim.worker_name,
    )
    return sim


@router.get("", response_model=PaginatedResponse[DependencyResponse])
async def list_dependencies(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    is_outdated: Optional[bool] = None,
    has_vulnerabilities: Optional[bool] = None,
    repository_id: Optional[UUID] = None,
    sort_by: str = Query("package_name"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
) -> PaginatedResponse[DependencyResponse]:
    from app.services.organizations import get_active_organization

    org = await get_active_organization(db, current_user)
    base_filter = [
        Repository.organization_id == org.id,
        Repository.deleted_at.is_(None),
    ]
    query = (
        select(Dependency)
        .join(Repository, Dependency.repository_id == Repository.id)
        .where(*base_filter)
    )
    count_query = (
        select(func.count())
        .select_from(Dependency)
        .join(Repository, Dependency.repository_id == Repository.id)
        .where(*base_filter)
    )

    if search:
        pattern = f"%{search}%"
        filt = or_(
            Dependency.package_name.ilike(pattern),
            Dependency.summary.ilike(pattern),
            Dependency.normalized_name.ilike(pattern),
        )
        query = query.where(filt)
        count_query = count_query.where(filt)
    if status_filter:
        query = query.where(Dependency.status == status_filter)
        count_query = count_query.where(Dependency.status == status_filter)
    if is_outdated is not None:
        query = query.where(Dependency.is_outdated == is_outdated)
        count_query = count_query.where(Dependency.is_outdated == is_outdated)
    if has_vulnerabilities is not None:
        query = query.where(Dependency.has_vulnerabilities == has_vulnerabilities)
        count_query = count_query.where(Dependency.has_vulnerabilities == has_vulnerabilities)
    if repository_id:
        query = query.where(Dependency.repository_id == repository_id)
        count_query = count_query.where(Dependency.repository_id == repository_id)

    sortable = {
        "package_name",
        "normalized_name",
        "ecosystem",
        "current_version",
        "latest_version",
        "is_outdated",
        "health_score",
        "risk_score",
        "usage_count",
        "vulnerability_count",
        "critical_vuln_count",
        "status",
        "created_at",
    }
    sort_col = (
        getattr(Dependency, sort_by)
        if sort_by in sortable
        else Dependency.package_name
    )
    query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    total = (await db.execute(count_query)).scalar_one()
    rows = (await db.execute(query)).scalars().all()
    return PaginatedResponse.create(
        items=[apply_osv_status(DependencyResponse.model_validate(r), r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{dependency_id}", response_model=DependencyDetailResponse)
async def get_dependency(
    dependency_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> DependencyDetailResponse:
    dep = await _get_owned_dependency(db, current_user, dependency_id)
    from app.services.upgrade_helpers import build_upgrade_advisor, collect_official_references

    detail = apply_osv_status(DependencyDetailResponse.model_validate(dep), dep)
    detail.upgrade_advisor = build_upgrade_advisor(
        package_name=dep.package_name,
        current_version=dep.current_version,
        latest_version=dep.latest_version,
        is_outdated=bool(dep.is_outdated),
        has_vulnerabilities=bool(dep.has_vulnerabilities),
        vulnerability_count=int(dep.vulnerability_count or 0),
        critical_vuln_count=int(dep.critical_vuln_count or 0),
        major_behind=int(dep.major_behind or 0),
        health_score=dep.health_score,
        risk_score=dep.risk_score,
        ai_should_update=dep.ai_should_update,
        usage_count=int(dep.usage_count or 0),
    )
    refs = collect_official_references(
        package_name=dep.package_name,
        pypi_url=dep.pypi_url,
        github_url=dep.github_repo_url,
        home_page=dep.home_page,
    )
    labeled: list[dict] = []
    for url in refs:
        label = "Documentation"
        lower = url.lower()
        if "pypi.org" in lower:
            label = "PyPI"
        elif "github.com" in lower and "/releases" in lower:
            label = "Release notes"
        elif "github.com" in lower:
            label = "GitHub"
        elif any(k in lower for k in ("changelog", "changes", "history")):
            label = "Changelog"
        elif any(k in lower for k in ("readthedocs", "docs.", "/doc")):
            label = "Documentation"
        labeled.append({"label": label, "url": url})
    detail.documentation_links = labeled
    meta = dep.extra_metadata if isinstance(dep.extra_metadata, dict) else {}
    detail.health_breakdown = meta.get("health_breakdown")
    try:
        from app.models.dependency_relationship import DependencyRelationship

        parents = (
            await db.execute(
                select(DependencyRelationship, Dependency)
                .join(
                    Dependency,
                    Dependency.id == DependencyRelationship.parent_dependency_id,
                )
                .where(
                    DependencyRelationship.repository_id == dep.repository_id,
                    DependencyRelationship.child_dependency_id == dep.id,
                )
            )
        ).all()
        detail.introduced_by = [
            {
                "parent_package": parent.package_name,
                "parent_dependency_id": str(parent.id),
                "relationship": rel.edge_type,
                "source": rel.source,
            }
            for rel, parent in parents
        ]
    except Exception:
        detail.introduced_by = []
    return detail


@router.get("/{dependency_id}/usages", response_model=PaginatedResponse[LibraryUsageResponse])
async def list_usages(
    dependency_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> PaginatedResponse[LibraryUsageResponse]:
    dep = await _get_owned_dependency(db, current_user, dependency_id)
    from app.models.library_usage import LibraryUsage

    count = (
        await db.execute(
            select(func.count()).select_from(LibraryUsage).where(LibraryUsage.dependency_id == dep.id)
        )
    ).scalar_one()
    rows = (
        await db.execute(
            select(LibraryUsage)
            .where(LibraryUsage.dependency_id == dep.id)
            .order_by(LibraryUsage.file_path, LibraryUsage.line)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return PaginatedResponse.create(
        items=[LibraryUsageResponse.model_validate(r) for r in rows],
        total=count,
        page=page,
        page_size=page_size,
    )


@router.get("/{dependency_id}/cves", response_model=list[CVEResponse])
async def list_cves(
    dependency_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[CVEResponse]:
    dep = await _get_owned_dependency(db, current_user, dependency_id)
    return [CVEResponse.model_validate(c) for c in dep.cves]


@router.get("/{dependency_id}/releases", response_model=list[ReleaseResponse])
async def list_releases(
    dependency_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[ReleaseResponse]:
    dep = await _get_owned_dependency(db, current_user, dependency_id)
    return [ReleaseResponse.model_validate(r) for r in dep.releases]


@router.get("/{dependency_id}/alternatives", response_model=list[AlternativeLibraryResponse])
async def list_alternatives(
    dependency_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[AlternativeLibraryResponse]:
    dep = await _get_owned_dependency(db, current_user, dependency_id)
    return [AlternativeLibraryResponse.model_validate(a) for a in dep.alternatives]


@router.get("/{dependency_id}/migrations", response_model=list[MigrationReportResponse])
async def list_migrations(
    dependency_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[MigrationReportResponse]:
    dep = await _get_owned_dependency(db, current_user, dependency_id)
    return [MigrationReportResponse.model_validate(m) for m in dep.migration_reports]


@router.post("/{dependency_id}/ai/refresh", response_model=DependencyResponse)
async def refresh_ai_analysis(
    dependency_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> DependencyResponse:
    dep = await _get_owned_dependency(db, current_user, dependency_id)
    await _reject_if_repository_archived(db, dep.repository_id)
    from app.services.organizations import get_active_organization
    from app.services.entitlements import require_ai_feature

    org = await get_active_organization(db, current_user)
    await require_ai_feature(db, org=org)

    from app.services.tasks.analysis_tasks import analyze_dependency_ai

    analyze_dependency_ai.delay(str(dep.id))
    return apply_osv_status(DependencyResponse.model_validate(dep), dep)


@router.post(
    "/{dependency_id}/analyze-upgrade-impact",
    status_code=status.HTTP_200_OK,
)
async def analyze_upgrade_impact(
    dependency_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    body: SimulateUpgradeRequest | None = None,
) -> dict:
    """
    Synchronous deterministic upgrade impact analysis.

    Uses catalog migration rules × repository AST usage only.
    Does not invent breaking changes. Unmatched used APIs are listed as unresolved.
    """
    from sqlalchemy import select

    from app.models.library_usage import LibraryUsage
    from app.services.organizations import get_active_organization
    from app.services.entitlements import require_upgrade_simulator
    from app.services.upgrade_impact import UpgradeImpactAnalyzer

    body = body or SimulateUpgradeRequest()
    dep = await _get_owned_dependency(db, current_user, dependency_id)
    await _reject_if_repository_archived(db, dep.repository_id)

    org = await get_active_organization(db, current_user)
    await require_upgrade_simulator(db, org=org)

    to_version = body.target_version or dep.latest_version
    if not to_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No target version available. Provide target_version or scan to discover latest.",
        )
    from_version = dep.current_version or "0.0.0"

    rows = (
        await db.execute(
            select(LibraryUsage).where(LibraryUsage.dependency_id == dep.id)
        )
    ).scalars().all()
    usages = [
        {
            "package_name": u.package_name,
            "symbol": u.symbol,
            "fully_qualified_name": u.fully_qualified_name,
            "usage_kind": u.usage_kind,
            "file_path": u.file_path,
            "line": u.line,
            "column": u.column,
            "code_snippet": u.code_snippet,
            "enclosing_function": u.enclosing_function,
            "enclosing_class": u.enclosing_class,
            "extra_metadata": u.extra_metadata or {},
        }
        for u in rows
    ]

    report = UpgradeImpactAnalyzer().analyze(
        package_name=dep.package_name,
        current_version=from_version,
        target_version=to_version,
        usages=usages,
    )
    from app.services.upgrade_intelligence import DynamicUpgradeIntelligence

    intelligence = DynamicUpgradeIntelligence().analyze(
        package_name=dep.package_name,
        current_version=from_version,
        target_version=to_version,
        usages=usages,
        ecosystem=dep.ecosystem or "PyPI",
        allow_ai=False,
        impact=report,
        skip_network=True,
        latest_version=dep.latest_version,
        github_url=dep.github_repo_url,
    )
    payload = report.model_dump()
    payload["dynamic_intelligence"] = intelligence.model_dump()
    payload["breaking_classification"] = intelligence.breaking_classification
    payload["analysis_method"] = intelligence.analysis_method
    payload["summary"] = intelligence.summary or report.summary
    return payload


@router.post(
    "/{dependency_id}/simulate-upgrade",
    response_model=UpgradeSimulationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def simulate_upgrade(
    dependency_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    body: SimulateUpgradeRequest | None = None,
) -> UpgradeSimulationResponse:
    """
    Start (or return cached) AI Upgrade Impact Simulation.

    Answers: What happens if I upgrade this dependency?
    Runs asynchronously; poll GET .../simulations/{id} for progress.
    """
    from sqlalchemy import select

    body = body or SimulateUpgradeRequest()
    dep = await _get_owned_dependency(db, current_user, dependency_id)
    await _reject_if_repository_archived(db, dep.repository_id)

    from app.services.organizations import get_active_organization
    from app.services.entitlements import record_feature_usage, require_upgrade_simulator

    org = await get_active_organization(db, current_user)
    # Upgrade Simulator = Free+ (analysis). AI Migration Assistant = Team+ (code).
    await require_upgrade_simulator(db, org=org)

    to_version = body.target_version or dep.latest_version
    if not to_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No target version available. Provide target_version or scan to discover latest.",
        )

    from_version = dep.current_version or "0.0.0"
    if from_version == to_version and not body.force_refresh:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Already on target version {to_version}. Pass force_refresh or a different target_version.",
        )

    # Sync-style helper expects sync session — run via greenlet-safe path using ORM objects already loaded
    from app.core.database import SyncSessionLocal
    from app.services.tasks.upgrade_simulation_tasks import (
        create_simulation_record,
        run_upgrade_simulation,
    )

    sync_db = SyncSessionLocal()
    created = False
    sim = None
    try:
        sync_dep = sync_db.get(Dependency, dep.id)
        if sync_dep is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")
        sim, created = create_simulation_record(
            sync_db,
            dependency=sync_dep,
            user_id=current_user.id,
            from_version=from_version,
            to_version=to_version,
            force_refresh=body.force_refresh,
        )
        # Durable row before Celery publish.
        sync_db.commit()
        if created:
            try:
                task = run_upgrade_simulation.delay(str(sim.id))
                sim.celery_task_id = task.id
                sync_db.commit()
            except Exception as exc:  # noqa: BLE001
                sim.status = SimulationStatus.FAILED.value
                sim.current_stage = "failed"
                sim.error_message = (
                    "Background processing service is unavailable. Please try again shortly."
                )
                sim.completed_at = job_utcnow()
                sync_db.commit()
                logger.error(
                    "simulation_dispatch_failed", simulation_id=str(sim.id), error=str(exc)
                )
        sync_db.refresh(sim)
        response = enrich_simulation_response(sim)
    finally:
        sync_db.close()

    if created and sim is not None:
        await record_feature_usage(
            db,
            organization_id=org.id,
            user_id=current_user.id,
            feature="upgrade_simulator",
            repository_id=dep.repository_id,
            dependency_id=dep.id,
            simulation_id=sim.id,
            meta={
                "package_name": dep.package_name,
                "from_version": from_version,
                "to_version": to_version,
                "plan": org.plan,
            },
        )
        await db.commit()

    return response


@router.get(
    "/{dependency_id}/simulations",
    response_model=list[UpgradeSimulationListItem],
)
async def list_simulations(
    dependency_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[UpgradeSimulationListItem]:
    await _get_owned_dependency(db, current_user, dependency_id)
    from sqlalchemy import select

    rows = (
        await db.execute(
            select(UpgradeSimulation)
            .where(UpgradeSimulation.dependency_id == dependency_id)
            .order_by(UpgradeSimulation.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return [UpgradeSimulationListItem.model_validate(r) for r in rows]


@router.get(
    "/{dependency_id}/simulations/{simulation_id}",
    response_model=UpgradeSimulationResponse,
)
async def get_simulation(
    dependency_id: UUID,
    simulation_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> UpgradeSimulationResponse:
    await _get_owned_dependency(db, current_user, dependency_id)
    from sqlalchemy import select

    result = await db.execute(
        select(UpgradeSimulation).where(
            UpgradeSimulation.id == simulation_id,
            UpgradeSimulation.dependency_id == dependency_id,
        )
    )
    sim = result.scalar_one_or_none()
    if sim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    sim = await _reconcile_simulation(db, sim)
    return enrich_simulation_response(sim)


async def _get_owned_simulation(
    db: DbSession,
    current_user: CurrentUser,
    dependency_id: UUID,
    simulation_id: UUID,
) -> UpgradeSimulation:
    await _get_owned_dependency(db, current_user, dependency_id)
    result = await db.execute(
        select(UpgradeSimulation).where(
            UpgradeSimulation.id == simulation_id,
            UpgradeSimulation.dependency_id == dependency_id,
        )
    )
    sim = result.scalar_one_or_none()
    if sim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    return sim


@router.post(
    "/{dependency_id}/simulations/{simulation_id}/cancel",
    response_model=UpgradeSimulationResponse,
)
async def cancel_simulation(
    dependency_id: UUID,
    simulation_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> UpgradeSimulationResponse:
    """Stop an in-flight simulation so the user is never stuck watching a spinner."""
    sim = await _get_owned_simulation(db, current_user, dependency_id, simulation_id)
    if sim.status in TERMINAL_SIMULATION_STATUSES:
        return enrich_simulation_response(sim)

    if sim.celery_task_id:
        try:
            from app.core.celery_app import celery_app

            celery_app.control.revoke(sim.celery_task_id, terminate=True)
        except Exception:  # noqa: BLE001
            logger.debug("simulation_revoke_failed", simulation_id=str(sim.id))

    now = job_utcnow()
    sim.cancel_requested = True
    sim.status = SimulationStatus.CANCELLED.value
    sim.current_stage = "cancelled"
    sim.completed_at = now
    sim.error_message = "Simulation cancelled by user"
    sim.stage_timings = close_stage_timings(sim.stage_timings, now=now)
    started = as_aware(sim.started_at)
    if started and sim.duration_seconds is None:
        sim.duration_seconds = (now - started).total_seconds()
    await db.commit()
    await db.refresh(sim)
    logger.info("simulation_cancelled", simulation_id=str(sim.id))
    return enrich_simulation_response(sim)


@router.post(
    "/{dependency_id}/simulations/{simulation_id}/retry",
    response_model=UpgradeSimulationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_simulation(
    dependency_id: UUID,
    simulation_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> UpgradeSimulationResponse:
    """Re-queue the same simulation record from stage one."""
    sim = await _get_owned_simulation(db, current_user, dependency_id, simulation_id)

    if sim.status in ACTIVE_SIMULATION_STATUSES and sim.celery_task_id:
        try:
            from app.core.celery_app import celery_app

            celery_app.control.revoke(sim.celery_task_id, terminate=True)
        except Exception:  # noqa: BLE001
            pass

    now = job_utcnow()
    sim.status = SimulationStatus.QUEUED.value
    sim.current_stage = "queued"
    sim.progress_percent = 0
    sim.error_message = None
    sim.started_at = None
    sim.completed_at = None
    sim.duration_seconds = None
    sim.queued_at = now
    sim.last_heartbeat_at = None
    sim.worker_name = None
    sim.cancel_requested = False
    sim.retry_count = (sim.retry_count or 0) + 1
    sim.stage_timings = []
    await db.flush()
    await db.commit()

    from app.services.tasks.upgrade_simulation_tasks import run_upgrade_simulation

    try:
        task = run_upgrade_simulation.delay(str(sim.id))
        sim.celery_task_id = task.id
    except Exception as exc:  # noqa: BLE001
        sim.status = SimulationStatus.FAILED.value
        sim.current_stage = "failed"
        sim.error_message = (
            "Background processing service is unavailable. Please try again shortly."
        )
        sim.completed_at = job_utcnow()
        logger.error("simulation_dispatch_failed", simulation_id=str(sim.id), error=str(exc))

    await db.commit()
    await db.refresh(sim)
    logger.info("simulation_retried", simulation_id=str(sim.id), retry_count=sim.retry_count)
    return enrich_simulation_response(sim)


@router.post(
    "/{dependency_id}/simulations/{simulation_id}/refresh",
    response_model=UpgradeSimulationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def refresh_simulation(
    dependency_id: UUID,
    simulation_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> UpgradeSimulationResponse:
    """Force a new simulation for the same from→to pair."""
    dep = await _get_owned_dependency(db, current_user, dependency_id)
    from sqlalchemy import select

    result = await db.execute(
        select(UpgradeSimulation).where(
            UpgradeSimulation.id == simulation_id,
            UpgradeSimulation.dependency_id == dependency_id,
        )
    )
    prior = result.scalar_one_or_none()
    if prior is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    body = SimulateUpgradeRequest(
        target_version=prior.to_version,
        force_refresh=True,
    )
    return await simulate_upgrade(dependency_id, current_user, db, body)


async def _reject_if_repository_archived(db: DbSession, repository_id: UUID) -> None:
    archived = (
        await db.execute(
            select(Repository.is_archived).where(Repository.id == repository_id)
        )
    ).scalar_one_or_none()
    if archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Archived repositories are read-only. Restore the repository to run new analysis.",
        )


async def _get_owned_dependency(
    db: DbSession,
    current_user: CurrentUser,
    dependency_id: UUID,
) -> Dependency:
    """Resolve a dependency in the caller's active organization (membership required)."""
    from app.services.organizations import get_active_organization

    org = await get_active_organization(db, current_user)
    result = await db.execute(
        select(Dependency)
        .join(Repository, Dependency.repository_id == Repository.id)
        .where(
            Dependency.id == dependency_id,
            Repository.organization_id == org.id,
            Repository.deleted_at.is_(None),
        )
        .options(
            selectinload(Dependency.versions),
            selectinload(Dependency.usages),
            selectinload(Dependency.cves),
            selectinload(Dependency.releases),
            selectinload(Dependency.alternatives),
            selectinload(Dependency.migration_reports),
        )
    )
    dep = result.scalar_one_or_none()
    if dep is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")
    return dep
