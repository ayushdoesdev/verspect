"""Alert endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps.auth import CurrentUser, DbSession
from app.core.enums import AlertStatus
from app.core.mixins import utcnow
from app.core.pagination import PaginatedResponse
from app.models.alert import Alert
from app.schemas.alert import AlertResponse, AlertUpdateRequest

router = APIRouter()


@router.get("", response_model=PaginatedResponse[AlertResponse])
async def list_alerts(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    severity: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    alert_type: Optional[str] = None,
    repository_id: Optional[UUID] = None,
) -> PaginatedResponse[AlertResponse]:
    query = select(Alert).where(Alert.user_id == current_user.id)
    count_query = select(func.count()).select_from(Alert).where(Alert.user_id == current_user.id)

    if severity:
        query = query.where(Alert.severity == severity)
        count_query = count_query.where(Alert.severity == severity)
    if status_filter:
        query = query.where(Alert.status == status_filter)
        count_query = count_query.where(Alert.status == status_filter)
    if alert_type:
        query = query.where(Alert.alert_type == alert_type)
        count_query = count_query.where(Alert.alert_type == alert_type)
    if repository_id:
        query = query.where(Alert.repository_id == repository_id)
        count_query = count_query.where(Alert.repository_id == repository_id)

    query = query.order_by(Alert.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    total = (await db.execute(count_query)).scalar_one()
    rows = (await db.execute(query)).scalars().all()
    return PaginatedResponse.create(
        items=[AlertResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: UUID,
    body: AlertUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> AlertResponse:
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == current_user.id)
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.status = body.status
    if body.status == AlertStatus.ACKNOWLEDGED.value:
        alert.acknowledged_at = utcnow()
    elif body.status == AlertStatus.RESOLVED.value:
        alert.resolved_at = utcnow()
    await db.flush()
    await db.refresh(alert)
    return AlertResponse.model_validate(alert)
