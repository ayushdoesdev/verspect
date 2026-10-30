"""Notification services — email and Slack."""

from __future__ import annotations

from email.message import EmailMessage
from typing import Any, Optional

import aiosmtplib
import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def send_email(
    to: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
) -> bool:
    if not to:
        logger.warning("email_skipped_no_recipient")
        return False
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    # Prefer 8bit over quoted-printable so reset tokens / URLs are not
    # soft-wrapped or "=3D"-encoded (which breaks password-reset links).
    message.set_content(body_text, charset="utf-8", cte="8bit")
    if body_html:
        message.add_alternative(body_html, subtype="html", charset="utf-8", cte="8bit")

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            start_tls=settings.smtp_tls,
        )
        logger.info("email_sent", to=to, subject=subject)
        return True
    except Exception as exc:
        logger.error("email_failed", to=to, error=str(exc))
        return False


async def send_slack(
    webhook_url: str,
    text: str,
    blocks: Optional[list[dict[str, Any]]] = None,
) -> bool:
    if not webhook_url:
        logger.warning("slack_skipped_no_webhook")
        return False
    payload: dict[str, Any] = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
        logger.info("slack_sent")
        return True
    except Exception as exc:
        logger.error("slack_failed", error=str(exc))
        return False


def format_alert_email(alert: dict[str, Any]) -> tuple[str, str, str]:
    subject = f"[{alert.get('severity', 'info').upper()}] {alert.get('title')}"
    text = (
        f"{alert.get('title')}\n\n"
        f"{alert.get('description')}\n\n"
        f"Recommendation: {alert.get('recommendation') or 'N/A'}\n"
        f"Type: {alert.get('alert_type')}\n"
        f"Severity: {alert.get('severity')}\n"
    )
    html = f"""
    <html><body>
    <h2>{alert.get('title')}</h2>
    <p><strong>Severity:</strong> {alert.get('severity')}</p>
    <p>{alert.get('description')}</p>
    <p><strong>Recommendation:</strong> {alert.get('recommendation') or 'N/A'}</p>
    </body></html>
    """
    return subject, text, html


def format_alert_slack(alert: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    text = f"*[{alert.get('severity', '').upper()}]* {alert.get('title')}"
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": alert.get("title", "Alert")[:150]},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Severity:*\n{alert.get('severity')}"},
                {"type": "mrkdwn", "text": f"*Type:*\n{alert.get('alert_type')}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": alert.get("description", "")[:2900]},
        },
    ]
    if alert.get("recommendation"):
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Recommendation:* {alert['recommendation'][:1000]}",
                },
            }
        )
    return text, blocks
