"""Bootstrap a platform admin for development / beta environments only."""

from __future__ import annotations

import secrets

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.user import User
from app.services.organizations import ensure_personal_organization

logger = get_logger(__name__)

DEFAULT_BOOTSTRAP_EMAIL = "admin@verspect.dev"
DEFAULT_BOOTSTRAP_PASSWORD = "Verspect@2026!"
DEFAULT_BOOTSTRAP_NAME = "Verspect Admin"


def _login_slug(email: str) -> str:
    local = email.split("@", 1)[0].lower()
    cleaned = "".join(c if c.isalnum() or c in "-_" else "-" for c in local)[:40]
    return f"{cleaned}-{secrets.token_hex(3)}"


async def ensure_bootstrap_admin() -> None:
    """
    If no platform admin exists and APP_ENV is development/beta, create one.

    Credentials come from BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD
    (defaults only for non-production envs). Never runs in production.
    """
    settings = get_settings()
    env = (settings.app_env or "").lower()
    if env not in {"development", "beta"}:
        return

    email = (settings.bootstrap_admin_email or DEFAULT_BOOTSTRAP_EMAIL).strip().lower()
    password = settings.bootstrap_admin_password or DEFAULT_BOOTSTRAP_PASSWORD
    name = (settings.bootstrap_admin_name or DEFAULT_BOOTSTRAP_NAME).strip()

    async with AsyncSessionLocal() as db:
        admin_count = (
            await db.execute(
                select(func.count())
                .select_from(User)
                .where(
                    User.is_admin.is_(True),
                    User.deleted_at.is_(None),
                )
            )
        ).scalar_one()

        existing = (
            await db.execute(
                select(User).where(User.email == email, User.deleted_at.is_(None))
            )
        ).scalar_one_or_none()

        if existing is not None:
            changed = False
            if not existing.is_admin:
                existing.is_admin = True
                changed = True
            if not existing.email_verified:
                existing.email_verified = True
                changed = True
            if not existing.is_active:
                existing.is_active = True
                changed = True
            if changed:
                await db.commit()
                logger.info("bootstrap_admin_flags_updated", email=email)
            return

        if int(admin_count or 0) > 0:
            # Another platform admin already exists — do not auto-create.
            logger.info(
                "bootstrap_admin_skipped_existing_admin",
                email=email,
                admin_count=int(admin_count or 0),
            )
            return

        user = User(
            github_login=_login_slug(email),
            email=email,
            name=name,
            password_hash=hash_password(password),
            auth_provider="email",
            email_verified=True,
            is_active=True,
            is_admin=True,
            onboarding_completed=True,
        )
        db.add(user)
        await db.flush()
        await ensure_personal_organization(db, user)
        await db.commit()
        logger.info("bootstrap_admin_created", email=email)
