"""Feedback submission schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

FeedbackCategory = Literal[
    "bug_report",
    "feature_request",
    "improvement",
    "question",
]
FeedbackStatus = Literal["open", "in_progress", "closed"]
FeedbackPriority = Literal["low", "medium", "high"]

ALLOWED_CATEGORIES = {
    "bug_report",
    "feature_request",
    "improvement",
    "question",
}
ALLOWED_STATUSES = {"open", "in_progress", "closed"}
ALLOWED_PRIORITIES = {"low", "medium", "high"}


class FeedbackCreate(BaseModel):
    category: FeedbackCategory
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10, max_length=8000)
    email: EmailStr
    repository: Optional[str] = Field(default=None, max_length=512)
    priority: FeedbackPriority = "medium"
    screenshot_data_url: Optional[str] = Field(default=None, max_length=3_500_000)
    page_url: Optional[str] = Field(default=None, max_length=1024)
    app_version: Optional[str] = Field(default=None, max_length=64)
    browser: Optional[str] = Field(default=None, max_length=512)

    @field_validator("title", "description", "repository", "page_url", "browser", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class FeedbackResponse(BaseModel):
    id: UUID
    category: str
    title: str
    description: str
    email: str
    repository: Optional[str] = None
    priority: str = "medium"
    has_screenshot: bool = False
    page_url: Optional[str] = None
    app_version: Optional[str] = None
    browser: Optional[str] = None
    status: str
    user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_row(cls, row) -> "FeedbackResponse":
        return cls(
            id=row.id,
            category=row.category,
            title=row.title,
            description=row.description,
            email=row.email,
            repository=row.repository,
            priority=getattr(row, "priority", None) or "medium",
            has_screenshot=bool(getattr(row, "screenshot_path", None)),
            page_url=row.page_url,
            app_version=row.app_version,
            browser=row.browser,
            status=row.status,
            user_id=row.user_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class FeedbackStatusUpdate(BaseModel):
    status: FeedbackStatus
