"""Shared Pydantic schema bases."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampSchema(ORMModel):
    created_at: datetime
    updated_at: datetime


class IDSchema(ORMModel):
    id: UUID


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None
