"""Alert, scan, dashboard, and search schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import IDSchema, TimestampSchema


class AlertResponse(IDSchema, TimestampSchema):
    user_id: UUID
    repository_id: Optional[UUID] = None
    dependency_id: Optional[UUID] = None
    alert_type: str
    severity: str
    status: str
    title: str
    description: str
    recommendation: Optional[str] = None
    fingerprint: str
    source_ref: Optional[str] = None
    affected_files: Optional[list] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    notified_at: Optional[datetime] = None


class AlertUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(open|acknowledged|resolved|ignored)$")


class ScanCreateRequest(BaseModel):
    scan_type: str = Field(default="manual", pattern="^(full|incremental|manual)$")


class ScanResponse(IDSchema, TimestampSchema):
    repository_id: UUID
    triggered_by_user_id: Optional[UUID] = None
    scan_type: str
    status: str
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    celery_task_id: Optional[str] = None
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    dependencies_found: int
    usages_found: int
    vulnerabilities_found: int
    alerts_created: int
    files_parsed: int
    outdated_count: int
    license_issues: int
    error_message: Optional[str] = None
    progress_percent: int
    current_stage: Optional[str] = None
    summary: Optional[dict] = None
    extra_metadata: Optional[dict] = None

    # Worker lifecycle / observability
    last_heartbeat_at: Optional[datetime] = None
    worker_name: Optional[str] = None
    retry_count: int = 0
    cancel_requested: bool = False
    stage_timings: Optional[list] = None
    # Computed per-request (not a column)
    queue_position: Optional[int] = None


class DashboardStats(BaseModel):
    repository_count: int
    dependency_count: int
    outdated_count: int
    critical_count: int
    warning_count: int
    average_health_score: Optional[float] = None
    vulnerable_count: int
    license_issue_count: int
    open_alert_count: int
    osv_unavailable_count: int = 0


class ChartDataPoint(BaseModel):
    label: str
    value: float
    meta: Optional[dict] = None


class DashboardCharts(BaseModel):
    dependency_distribution: List[ChartDataPoint]
    outdated_trend: List[ChartDataPoint]
    health_scores: List[ChartDataPoint]
    severity_breakdown: List[ChartDataPoint]


class DashboardResponse(BaseModel):
    stats: DashboardStats
    charts: DashboardCharts
    latest_releases: list
    critical_cves: list
    recent_alerts: list


class SearchRequest(BaseModel):
    q: str = Field(..., min_length=1, max_length=256)
    types: Optional[List[str]] = Field(
        default=None,
        description="Filter: dependency, repository, file, function",
    )
    limit: int = Field(default=25, ge=1, le=100)


class SearchHit(BaseModel):
    type: str
    id: str
    title: str
    subtitle: Optional[str] = None
    url: str
    score: float = 1.0
    meta: Optional[dict] = None


class SearchResponse(BaseModel):
    query: str
    total: int
    hits: List[SearchHit]
