"""Public contact / Request Demo submissions."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps.auth import DbSession
from app.core.logging import get_logger
from app.core.rate_limit import contact_rate_limiter
from app.models.contact_request import ContactRequest
from app.schemas.contact import ContactCreate, ContactResponse

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_contact_request(
    body: ContactCreate,
    request: Request,
    db: DbSession,
) -> ContactRequest:
    client = request.client.host if request.client else "unknown"
    if not contact_rate_limiter.allow(f"contact:{client}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many contact requests. Please try again shortly.",
        )

    row = ContactRequest(
        name=body.name,
        company=body.company or None,
        email=str(body.email).lower(),
        team_size=body.team_size or None,
        message=body.message,
        status="open",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info("contact_request_submitted", contact_id=str(row.id), email=row.email)
    return row
