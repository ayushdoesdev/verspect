"""Dashboard aggregation endpoints."""

from fastapi import APIRouter
from sqlalchemy import case, func, select

from app.api.deps.auth import CurrentUser, DbSession
from app.core.enums import AlertSeverity, AlertStatus
from app.models.alert import Alert
from app.models.cve import CVE
from app.models.dependency import Dependency
from app.models.release import Release
from app.models.repository import Repository
from app.schemas.alert import (
    ChartDataPoint,
    DashboardCharts,
    DashboardResponse,
    DashboardStats,
)
from app.schemas.alert import AlertResponse
from app.schemas.dependency import CVEResponse, ReleaseResponse

router = APIRouter()


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    current_user: CurrentUser,
    db: DbSession,
) -> DashboardResponse:
    from app.services.organizations import get_active_organization

    org = await get_active_organization(db, current_user)
    owner_filter = (
        Repository.organization_id == org.id,
        Repository.deleted_at.is_(None),
    )

    repo_count = (
        await db.execute(select(func.count()).select_from(Repository).where(*owner_filter))
    ).scalar_one()

    dep_stats = (
        await db.execute(
            select(
                func.count(Dependency.id),
                func.coalesce(func.sum(case((Dependency.is_outdated.is_(True), 1), else_=0)), 0),
                func.coalesce(
                    func.sum(case((Dependency.has_vulnerabilities.is_(True), 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case((Dependency.license_policy_action == "reject", 1), else_=0)
                    ),
                    0,
                ),
                func.avg(Dependency.health_score),
                func.coalesce(func.sum(Dependency.critical_vuln_count), 0),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Dependency.extra_metadata.op("->>")("osv_status")
                                == "unavailable",
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
            )
            .select_from(Dependency)
            .join(Repository, Dependency.repository_id == Repository.id)
            .where(*owner_filter)
        )
    ).one()

    open_alerts = (
        await db.execute(
            select(func.count())
            .select_from(Alert)
            .where(
                Alert.user_id == current_user.id,
                Alert.status == AlertStatus.OPEN.value,
            )
        )
    ).scalar_one()

    warning_count = (
        await db.execute(
            select(func.count())
            .select_from(Alert)
            .where(
                Alert.user_id == current_user.id,
                Alert.status == AlertStatus.OPEN.value,
                Alert.severity.in_(
                    [AlertSeverity.MEDIUM.value, AlertSeverity.LOW.value, AlertSeverity.HIGH.value]
                ),
            )
        )
    ).scalar_one()

    stats = DashboardStats(
        repository_count=repo_count,
        dependency_count=int(dep_stats[0] or 0),
        outdated_count=int(dep_stats[1] or 0),
        critical_count=int(dep_stats[5] or 0),
        warning_count=int(warning_count or 0),
        average_health_score=float(dep_stats[4]) if dep_stats[4] is not None else None,
        vulnerable_count=int(dep_stats[2] or 0),
        license_issue_count=int(dep_stats[3] or 0),
        open_alert_count=int(open_alerts or 0),
        osv_unavailable_count=int(dep_stats[6] or 0),
    )

    # Status distribution chart
    status_rows = (
        await db.execute(
            select(Dependency.status, func.count(Dependency.id))
            .join(Repository, Dependency.repository_id == Repository.id)
            .where(*owner_filter)
            .group_by(Dependency.status)
        )
    ).all()
    distribution = [
        ChartDataPoint(label=row[0] or "unknown", value=float(row[1])) for row in status_rows
    ]

    # Health scores per repository
    health_rows = (
        await db.execute(
            select(Repository.name, Repository.health_score)
            .where(*owner_filter)
            .order_by(Repository.health_score.desc().nullslast())
            .limit(10)
        )
    ).all()
    health_scores = [
        ChartDataPoint(label=row[0], value=float(row[1] or 0)) for row in health_rows
    ]

    # Severity breakdown
    sev_rows = (
        await db.execute(
            select(Alert.severity, func.count(Alert.id))
            .where(Alert.user_id == current_user.id, Alert.status == AlertStatus.OPEN.value)
            .group_by(Alert.severity)
        )
    ).all()
    severity_breakdown = [
        ChartDataPoint(label=row[0], value=float(row[1])) for row in sev_rows
    ]

    # Outdated trend — approximate using major/minor/patch buckets
    outdated_trend = [
        ChartDataPoint(label="Major behind", value=float(
            (await db.execute(
                select(func.count())
                .select_from(Dependency)
                .join(Repository)
                .where(*owner_filter, Dependency.major_behind > 0)
            )).scalar_one()
        )),
        ChartDataPoint(label="Minor behind", value=float(
            (await db.execute(
                select(func.count())
                .select_from(Dependency)
                .join(Repository)
                .where(*owner_filter, Dependency.major_behind == 0, Dependency.minor_behind > 0)
            )).scalar_one()
        )),
        ChartDataPoint(label="Patch behind", value=float(
            (await db.execute(
                select(func.count())
                .select_from(Dependency)
                .join(Repository)
                .where(
                    *owner_filter,
                    Dependency.major_behind == 0,
                    Dependency.minor_behind == 0,
                    Dependency.patch_behind > 0,
                )
            )).scalar_one()
        )),
    ]

    charts = DashboardCharts(
        dependency_distribution=distribution,
        outdated_trend=outdated_trend,
        health_scores=health_scores,
        severity_breakdown=severity_breakdown,
    )

    latest_releases = (
        await db.execute(
            select(Release)
            .join(Dependency, Release.dependency_id == Dependency.id)
            .join(Repository, Dependency.repository_id == Repository.id)
            .where(*owner_filter)
            .order_by(Release.released_at.desc().nullslast(), Release.created_at.desc())
            .limit(10)
        )
    ).scalars().all()

    critical_cves = (
        await db.execute(
            select(CVE)
            .join(Dependency, CVE.dependency_id == Dependency.id)
            .join(Repository, Dependency.repository_id == Repository.id)
            .where(*owner_filter, CVE.severity == AlertSeverity.CRITICAL.value)
            .order_by(CVE.cvss_score.desc().nullslast())
            .limit(10)
        )
    ).scalars().all()

    recent_alerts = (
        await db.execute(
            select(Alert)
            .where(Alert.user_id == current_user.id)
            .order_by(Alert.created_at.desc())
            .limit(10)
        )
    ).scalars().all()

    return DashboardResponse(
        stats=stats,
        charts=charts,
        latest_releases=[ReleaseResponse.model_validate(r).model_dump() for r in latest_releases],
        critical_cves=[CVEResponse.model_validate(c).model_dump() for c in critical_cves],
        recent_alerts=[AlertResponse.model_validate(a).model_dump() for a in recent_alerts],
    )
