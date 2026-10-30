"""Organization / team schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import IDSchema, TimestampSchema


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: Optional[str] = Field(default=None, max_length=120)


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None


class LicensePolicyUpdate(BaseModel):
    """SPDX-like identifiers for org license policy. Empty lists clear that bucket."""

    reject: Optional[list[str]] = None
    warn: Optional[list[str]] = None


class LicensePolicyResponse(BaseModel):
    reject: list[str]
    warn: list[str]
    source: str


class OrganizationResponse(IDSchema, TimestampSchema):
    name: str
    slug: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    plan: str
    is_personal: bool
    owner_user_id: UUID
    role: Optional[str] = None
    license_policy: Optional[LicensePolicyResponse] = None


class MemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    role: str
    email: Optional[str] = None
    name: Optional[str] = None
    github_login: Optional[str] = None
    avatar_url: Optional[str] = None
    joined_at: Optional[datetime] = None


class InviteCreate(BaseModel):
    email: EmailStr
    role: str = "developer"


class InvitationResponse(IDSchema, TimestampSchema):
    email: str
    role: str
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    token: Optional[str] = None


class MemberRoleUpdate(BaseModel):
    role: str


class SwitchOrganizationRequest(BaseModel):
    organization_id: UUID
