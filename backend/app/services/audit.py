"""Audit log writer — used when plan entitlements include audit_logs."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.services.plans import get_plan_limits


async def record_audit_event(
    db: AsyncSession,
    *,
    organization_id: Optional[UUID],
    plan: str,
    actor_user_id: Optional[UUID],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> Optional[AuditLog]:
    """Persist an audit event when the org plan includes audit logs (Team+)."""
    if organization_id is None:
        return None
    limits = get_plan_limits(plan)
    if not limits.audit_logs:
        return None
    entry = AuditLog(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        details=details or {},
    )
    db.add(entry)
    await db.flush()
    return entry
