"""Public feedback submission for Private Beta."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps.auth import DbSession, OptionalUser
from app.core.logging import get_logger
from app.core.rate_limit import feedback_rate_limiter
from app.models.feedback import FeedbackSubmission
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.services.feedback_storage import save_feedback_screenshot

router = APIRouter()
logger = get_logger(__name__)

APP_VERSION = "1.0.0"


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_feedback(
    body: FeedbackCreate,
    request: Request,
    db: DbSession,
    current_user: OptionalUser,
) -> FeedbackResponse:
    client = request.client.host if request.client else "unknown"
    if not feedback_rate_limiter.allow(f"feedback:{client}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many feedback submissions. Please try again shortly.",
        )

    row = FeedbackSubmission(
        category=body.category,
        title=body.title,
        description=body.description,
        email=str(body.email).lower(),
        repository=body.repository or None,
        priority=body.priority,
        page_url=body.page_url or None,
        app_version=(body.app_version or APP_VERSION)[:64],
        browser=(body.browser or None),
        status="open",
        user_id=current_user.id if current_user else None,
    )
    db.add(row)
    await db.flush()

    if body.screenshot_data_url:
        row.screenshot_path = save_feedback_screenshot(
            feedback_id=row.id,
            screenshot_data_url=body.screenshot_data_url,
        )

    await db.commit()
    await db.refresh(row)
    logger.info(
        "feedback_submitted",
        feedback_id=str(row.id),
        category=row.category,
        priority=row.priority,
        has_screenshot=bool(row.screenshot_path),
        user_id=str(row.user_id) if row.user_id else None,
    )
    return FeedbackResponse.from_row(row)
