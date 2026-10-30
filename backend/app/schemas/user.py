"""User and auth schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import IDSchema, TimestampSchema


class UserBase(BaseModel):
    github_login: str
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserSettingsUpdate(BaseModel):
    email_notifications: Optional[bool] = None
    slack_notifications: Optional[bool] = None
    slack_webhook_url: Optional[str] = None
    notify_on_critical_cve: Optional[bool] = None
    notify_on_major_release: Optional[bool] = None
    notify_on_license_violation: Optional[bool] = None
    license_policy_override: Optional[dict] = None
    settings: Optional[dict] = None
    onboarding_completed: Optional[bool] = None


class UserResponse(UserBase, IDSchema, TimestampSchema):
    github_id: Optional[int] = None
    google_id: Optional[str] = None
    auth_provider: str = "github"
    email_verified: bool = False
    is_active: bool
    is_admin: bool
    onboarding_completed: bool = False
    active_organization_id: Optional[UUID] = None
    email_notifications: bool
    slack_notifications: bool
    slack_webhook_url: Optional[str] = None
    notify_on_critical_cve: bool
    notify_on_major_release: bool
    notify_on_license_violation: bool
    last_login_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


class GitHubAuthURLResponse(BaseModel):
    authorization_url: str
    state: str


class GitHubCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None


class OAuthExchangeRequest(BaseModel):
    """One-time login ticket from the OAuth callback redirect (not a JWT)."""

    code: str = Field(min_length=16, max_length=256)


class EmailRegisterRequest(BaseModel):
    email: EmailStr
    # bcrypt hard-limit is 72 bytes; keep char max aligned for ASCII passwords.
    password: str = Field(min_length=8, max_length=72)
    name: Optional[str] = None
    remember_me: bool = False


class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=72)
    remember_me: bool = False


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=72)


class VerifyEmailRequest(BaseModel):
    token: str


class GoogleAuthURLResponse(BaseModel):
    authorization_url: str
    state: str
