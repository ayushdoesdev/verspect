"""Contact / Request Demo schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class ContactCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    company: Optional[str] = Field(default=None, max_length=255)
    email: EmailStr
    team_size: Optional[str] = Field(default=None, max_length=64)
    message: str = Field(min_length=10, max_length=8000)

    @field_validator("name", "company", "team_size", "message", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ContactResponse(BaseModel):
    id: UUID
    name: str
    company: Optional[str] = None
    email: str
    team_size: Optional[str] = None
    message: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
