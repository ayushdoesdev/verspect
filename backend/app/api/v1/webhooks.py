"""Inbound webhooks — GitHub + billing providers."""

import hashlib
import hmac
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps.auth import DbSession
from app.core.config import get_settings
from app.core.enums import ScanStatus, ScanType
from app.core.logging import get_logger
from app.models.repository import Repository
from app.models.scan import Scan
from app.services.billing.factory import BillingProviderFactory

router = APIRouter()
settings = get_settings()
logger = get_logger(__name__)


@router.post("/stripe")
async def stripe_billing_webhook(request: Request, db: DbSession) -> dict[str, Any]:
    """Stripe billing events — independent of Razorpay."""
    payload = await request.body()
    provider = BillingProviderFactory.for_webhook("stripe")
    try:
        return await provider.handle_webhook(db, payload, dict(request.headers))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/razorpay")
async def razorpay_billing_webhook(request: Request, db: DbSession) -> dict[str, Any]:
    """Razorpay billing events — independent of Stripe."""
    payload = await request.body()
    provider = BillingProviderFactory.for_webhook("razorpay")
    try:
        return await provider.handle_webhook(db, payload, dict(request.headers))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc



def verify_github_signature(payload: bytes, signature_header: str | None) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = signature_header.removeprefix("sha256=")
    digest = hmac.new(
        settings.github_webhook_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, expected)


@router.post("/github")
async def github_webhook(
    request: Request,
    db: DbSession,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
    x_github_delivery: str | None = Header(None),
) -> dict[str, Any]:
    body = await request.body()
    if not verify_github_signature(body, x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    payload = await request.json()
    event = x_github_event or "unknown"
    logger.info(
        "github_webhook_received",
        event=event,
        delivery=x_github_delivery,
    )

    if event == "ping":
        return {"status": "pong"}

    repo_info = payload.get("repository") or {}
    github_repo_id = repo_info.get("id")
    if not github_repo_id:
        return {"status": "ignored", "reason": "no repository"}

    result = await db.execute(
        select(Repository).where(
            Repository.github_repo_id == github_repo_id,
            Repository.deleted_at.is_(None),
            Repository.is_watching.is_(True),
            Repository.is_archived.is_(False),
        )
    )
    repos = result.scalars().all()
    if not repos:
        return {"status": "ignored", "reason": "repository not watched"}

    from app.models.billing import Subscription
    from app.models.organization import Organization
    from app.services.entitlements import resolve_entitlements

    triggered = []
    for repo in repos:
        # Webhook-triggered scans require active Pro+ webhooks entitlement.
        if not repo.organization_id:
            continue
        org = (
            await db.execute(
                select(Organization).where(Organization.id == repo.organization_id)
            )
        ).scalar_one_or_none()
        if org is None:
            continue
        sub = (
            await db.execute(
                select(Subscription).where(Subscription.organization_id == org.id)
            )
        ).scalar_one_or_none()
        ents = resolve_entitlements(org, sub)
        if not ents.webhooks or not ents.can_run_background_jobs:
            continue

        if event == "push":
            after_sha = payload.get("after")
            if after_sha and after_sha == repo.last_commit_sha:
                continue
            scan = Scan(
                repository_id=repo.id,
                triggered_by_user_id=repo.owner_id,
                scan_type=ScanType.WEBHOOK.value,
                branch=payload.get("ref", "").removeprefix("refs/heads/") or repo.default_branch,
                previous_commit_sha=payload.get("before") or repo.last_commit_sha,
                commit_sha=after_sha,
                status=ScanStatus.QUEUED.value,
                extra_metadata={"event": event, "delivery": x_github_delivery},
            )
            db.add(scan)
            await db.flush()
            await db.commit()
            from app.services.tasks.scan_tasks import run_repository_scan

            task = run_repository_scan.delay(str(scan.id))
            scan.celery_task_id = task.id
            triggered.append(str(scan.id))
            await db.flush()

        elif event in ("release", "repository"):
            scan = Scan(
                repository_id=repo.id,
                triggered_by_user_id=repo.owner_id,
                scan_type=ScanType.WEBHOOK.value,
                branch=repo.default_branch,
                status=ScanStatus.QUEUED.value,
                extra_metadata={"event": event, "delivery": x_github_delivery},
            )
            db.add(scan)
            await db.flush()
            await db.commit()
            from app.services.tasks.scan_tasks import run_repository_scan

            task = run_repository_scan.delay(str(scan.id))
            scan.celery_task_id = task.id
            triggered.append(str(scan.id))
            await db.flush()

    await db.flush()
    return {"status": "accepted", "scans": triggered, "event": event}
