"""Celery tasks — notifications."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.database import SyncSessionLocal
from app.core.logging import get_logger
from app.models.user import User
from app.notifications.channels import (
    format_alert_email,
    format_alert_slack,
    send_email,
    send_slack,
)

logger = get_logger(__name__)
settings = get_settings()


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task(name="app.services.tasks.notification_tasks.notify_alert")
def notify_alert(user_id: str, alert: dict[str, Any]) -> dict[str, Any]:
    session = SyncSessionLocal()
    try:
        user = session.get(User, UUID(user_id))
        if user is None:
            return {"error": "user_not_found"}

        severity = (alert.get("severity") or "").lower()
        alert_type = (alert.get("alert_type") or "").lower()

        should_email = user.email_notifications and user.email
        should_slack = user.slack_notifications and (
            user.slack_webhook_url or settings.slack_webhook_url
        )

        if alert_type == "cve" and severity == "critical" and not user.notify_on_critical_cve:
            should_email = False
            should_slack = False
        if alert_type == "major_release" and not user.notify_on_major_release:
            should_email = should_email and False
            should_slack = False
        if alert_type in {"license_violation", "license_warning"} and not user.notify_on_license_violation:
            should_email = False
            should_slack = False

        results: dict[str, Any] = {"email": False, "slack": False}

        async def _send() -> None:
            nonlocal results
            if should_email:
                subject, text, html = format_alert_email(alert)
                results["email"] = await send_email(user.email, subject, text, html)
            if should_slack:
                webhook = user.slack_webhook_url or settings.slack_webhook_url
                text, blocks = format_alert_slack(alert)
                results["slack"] = await send_slack(webhook, text, blocks)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Inside existing loop — schedule
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(lambda: asyncio.run(_send())).result()
            else:
                loop.run_until_complete(_send())
        except RuntimeError:
            asyncio.run(_send())

        logger.info("notify_alert_done", user_id=user_id, results=results)
        return results
    finally:
        session.close()
