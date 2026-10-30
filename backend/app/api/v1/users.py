"""User profile and settings endpoints."""

from fastapi import APIRouter

from app.api.deps.auth import CurrentUser, DbSession
from app.schemas.user import UserResponse, UserSettingsUpdate

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_profile(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_settings(
    body: UserSettingsUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> UserResponse:
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(current_user, key, value)
    await db.flush()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)
