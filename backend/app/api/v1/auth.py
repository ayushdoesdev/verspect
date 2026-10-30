"""Authentication — GitHub, Google, email/password."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.api.deps.auth import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.user import (
    EmailLoginRequest,
    EmailRegisterRequest,
    ForgotPasswordRequest,
    GitHubAuthURLResponse,
    GoogleAuthURLResponse,
    LogoutRequest,
    OAuthExchangeRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.github import github_auth_service
from app.services.oauth_flow import frontend_login_redirect, get_oauth_flow
from app.services.organizations import ensure_personal_organization
from app.services.token_revoke import is_refresh_token_revoked, revoke_refresh_token

router = APIRouter()
settings = get_settings()


def _tokens_for(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, extra_claims={"login": user.github_login}),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


def _login_slug_from_email(email: str) -> str:
    local = email.split("@", 1)[0].lower()
    cleaned = "".join(c if c.isalnum() or c in "-_" else "-" for c in local)[:40]
    return f"{cleaned}-{secrets.token_hex(3)}"


def _oauth_error_redirect(message: str) -> RedirectResponse:
    return RedirectResponse(
        url=f"{settings.app_url.rstrip('/')}/login?{urlencode({'error': message})}",
        status_code=302,
    )


@router.get("/github/url", response_model=GitHubAuthURLResponse)
async def github_auth_url() -> GitHubAuthURLResponse:
    flow = get_oauth_flow()
    state = flow.issue_state("github")
    url, _ = github_auth_service.get_authorization_url(state=state)
    return GitHubAuthURLResponse(authorization_url=url, state=state)


@router.get("/github/callback")
async def github_callback(
    db: DbSession,
    code: str = Query(...),
    state: str | None = Query(None),
) -> RedirectResponse:
    flow = get_oauth_flow()
    try:
        flow.consume_state(state, provider="github")
    except ValueError:
        return _oauth_error_redirect("Invalid or expired sign-in session. Please try again.")

    try:
        tokens = await github_auth_service.authenticate_with_code(db, code)
        await db.commit()
    except Exception:  # noqa: BLE001
        return _oauth_error_redirect("GitHub authentication failed. Please try again.")

    ticket = flow.issue_login_ticket(user_id=tokens.user.id, provider="github")
    return RedirectResponse(
        url=frontend_login_redirect(settings.app_url, ticket),
        status_code=302,
    )


@router.post("/oauth/exchange", response_model=TokenResponse)
async def oauth_exchange_login_code(
    db: DbSession,
    body: OAuthExchangeRequest,
) -> TokenResponse:
    """Exchange a one-time OAuth login ticket for JWTs (never accept JWTs from the URL)."""
    flow = get_oauth_flow()
    try:
        ticket = flow.consume_login_ticket(body.code)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    result = await db.execute(
        select(User).where(User.id == ticket.user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return _tokens_for(user)


@router.get("/google/url", response_model=GoogleAuthURLResponse)
async def google_auth_url() -> GoogleAuthURLResponse:
    if not settings.google_client_id:
        raise HTTPException(status_code=400, detail="Google OAuth is not configured")
    flow = get_oauth_flow()
    state = flow.issue_state("google")
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return GoogleAuthURLResponse(authorization_url=url, state=state)


@router.get("/google/callback")
async def google_callback(
    db: DbSession,
    code: str = Query(...),
    state: str | None = Query(None),
) -> RedirectResponse:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=400, detail="Google OAuth is not configured")

    flow = get_oauth_flow()
    try:
        flow.consume_state(state, provider="google")
    except ValueError:
        return _oauth_error_redirect("Invalid or expired sign-in session. Please try again.")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_resp.raise_for_status()
            access = token_resp.json()["access_token"]
            profile = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access}"},
            )
            profile.raise_for_status()
            info = profile.json()
    except Exception:  # noqa: BLE001
        return _oauth_error_redirect("Google authentication failed. Please try again.")

    google_id = str(info["id"])
    email = info.get("email")
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()
    if user is None and email:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
    if user is None:
        user = User(
            github_login=_login_slug_from_email(email or f"google-{google_id}"),
            google_id=google_id,
            email=email,
            name=info.get("name"),
            avatar_url=info.get("picture"),
            auth_provider="google",
            email_verified=bool(info.get("verified_email")),
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()
    else:
        user.google_id = google_id
        user.auth_provider = "google"
        user.email = email or user.email
        user.name = info.get("name") or user.name
        user.avatar_url = info.get("picture") or user.avatar_url
        user.email_verified = True
        user.last_login_at = datetime.now(timezone.utc)

    await ensure_personal_organization(db, user)
    await db.commit()
    ticket = flow.issue_login_ticket(user_id=user.id, provider="google")
    return RedirectResponse(
        url=frontend_login_redirect(settings.app_url, ticket),
        status_code=302,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_email(db: DbSession, body: EmailRegisterRequest) -> TokenResponse:
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    user = User(
        github_login=_login_slug_from_email(body.email),
        email=body.email.lower(),
        name=body.name,
        password_hash=hash_password(body.password),
        auth_provider="email",
        email_verified=False,
        email_verification_token=secrets.token_urlsafe(32),
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    await ensure_personal_organization(db, user)
    await db.commit()
    await db.refresh(user)
    # In production, email the verification token via SMTP
    return _tokens_for(user)


@router.post("/login", response_model=TokenResponse)
async def login_email(db: DbSession, body: EmailLoginRequest) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email.lower(), User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    user.last_login_at = datetime.now(timezone.utc)
    await ensure_personal_organization(db, user)
    await db.commit()
    await db.refresh(user)
    return _tokens_for(user)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(db: DbSession, body: ForgotPasswordRequest) -> MessageResponse:
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if user:
        token = secrets.token_urlsafe(32)
        user.password_reset_token = token
        user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
        await db.commit()
        from app.notifications.channels import send_email

        reset_url = f"{settings.app_url.rstrip('/')}/reset-password?token={token}"
        await send_email(
            to=user.email or body.email.lower(),
            subject="Reset your Verspect password",
            body_text=(
                "We received a request to reset your password.\n\n"
                f"Open this link within 2 hours:\n{reset_url}\n\n"
                "If you did not request this, you can ignore this email."
            ),
        )
    return MessageResponse(message="If that email exists, a reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(db: DbSession, body: ResetPasswordRequest) -> MessageResponse:
    result = await db.execute(
        select(User).where(User.password_reset_token == body.token, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if user is None or not user.password_reset_expires_at:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    if user.password_reset_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset token expired")
    user.password_hash = hash_password(body.password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    await db.commit()
    return MessageResponse(message="Password updated successfully")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(db: DbSession, body: VerifyEmailRequest) -> MessageResponse:
    result = await db.execute(
        select(User).where(User.email_verification_token == body.token, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    user.email_verified = True
    user.email_verification_token = None
    await db.commit()
    return MessageResponse(message="Email verified")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(db: DbSession, body: RefreshTokenRequest) -> TokenResponse:
    if is_refresh_token_revoked(body.refresh_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked",
        )
    try:
        payload = decode_token(body.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    result = await db.execute(select(User).where(User.id == payload["sub"], User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return _tokens_for(user)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    _current_user: CurrentUser,
    body: LogoutRequest | None = None,
) -> MessageResponse:
    token = body.refresh_token if body else None
    if token:
        ttl_seconds = settings.jwt_refresh_token_expire_days * 24 * 60 * 60
        revoke_refresh_token(token, ttl_seconds=ttl_seconds)
    return MessageResponse(message="Logged out successfully")
