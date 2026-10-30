"""AI provider health and settings — provider-agnostic."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps.auth import CurrentUser, DbSession
from app.ai.providers.factory import AIProviderFactory, SUPPORTED_PROVIDERS
from app.ai.service import AIService

router = APIRouter()


class AIHealthResponse(BaseModel):
    provider: str
    model: str
    available: bool
    latency_ms: float | None = None
    status: str = "unknown"
    message: str | None = None
    fallbacks: list[str] = Field(default_factory=list)


class AISettingsResponse(BaseModel):
    configured_provider: str
    configured_model: str
    active_provider: str | None = None
    active_model: str | None = None
    available: bool = False
    connection_status: str | None = None
    latency_ms: float | None = None
    health_message: str | None = None
    fallback_providers: list[str] = Field(default_factory=list)
    supported_providers: list[str] = Field(default_factory=list)
    ollama_base_url: str | None = None
    ollama_model: str | None = None


class AIChatRequest(BaseModel):
    message: str
    system: str = ""
    history: list[dict[str, str]] = Field(default_factory=list)
    repository_id: str | None = None


class AIChatResponse(BaseModel):
    reply: str
    provider: str
    model: str
    repository_id: str | None = None
    errors: list[str] | None = None


@router.get("/health", response_model=AIHealthResponse)
async def ai_health() -> AIHealthResponse:
    """
    Public AI connectivity probe.

    Returns provider, model, available, latency — used by ops and the settings UI.
    """
    data = AIService().health()
    return AIHealthResponse(**data)


@router.get("/settings", response_model=AISettingsResponse)
async def ai_settings(_user: CurrentUser) -> AISettingsResponse:
    """Current provider / model / connection status for the AI settings page."""
    data = AIService().settings_snapshot()
    return AISettingsResponse(**data)


@router.get("/providers")
async def list_providers(_user: CurrentUser) -> dict:
    return {
        "supported": list(SUPPORTED_PROVIDERS),
        "fallback_chain": AIProviderFactory.fallback_chain(),
        "defaults": {
            name: AIProviderFactory._resolve_model(name, AIService().settings, None)
            for name in SUPPORTED_PROVIDERS
        },
    }


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(
    body: AIChatRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> AIChatResponse:
    """Repository Chat — Pro+ only. Routes through the pluggable provider interface."""
    from app.services.entitlements import require_ai_feature
    from app.services.organizations import get_active_organization

    org = await get_active_organization(db, current_user)
    await require_ai_feature(db, org=org)
    result = AIService().chat(
        message=body.message,
        system=body.system,
        history=body.history,
        repository_id=body.repository_id,
    )
    return AIChatResponse(**result)
