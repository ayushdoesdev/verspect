"""AIProviderFactory — select provider from AI_PROVIDER env var.

Add a new provider by:
  1. Implementing AIProvider (complete + is_available)
  2. Registering it in SUPPORTED_PROVIDERS / DEFAULT_MODELS / create()
Business services never change.
"""

from __future__ import annotations

from typing import Optional

from app.ai.exceptions import AIProviderUnavailable
from app.ai.providers.base import AIProvider
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.groq_provider import GroqProvider
from app.ai.providers.ollama_provider import OllamaProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.ai.providers.openrouter_provider import OpenRouterProvider
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

SUPPORTED_PROVIDERS = ("ollama", "openai", "gemini", "groq", "openrouter")

DEFAULT_MODELS = {
    "ollama": "qwen3:8b",
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-2.0-flash",
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "openai/gpt-4o-mini",
}


class AIProviderFactory:
    """Create provider instances from configuration."""

    @classmethod
    def create(
        cls,
        name: Optional[str] = None,
        *,
        settings: Optional[Settings] = None,
        model: Optional[str] = None,
    ) -> AIProvider:
        settings = settings or get_settings()
        provider_name = (name or settings.ai_provider or "ollama").strip().lower()
        if provider_name not in SUPPORTED_PROVIDERS:
            raise AIProviderUnavailable(
                provider_name,
                f"Unsupported AI_PROVIDER={provider_name!r}. "
                f"Supported: {', '.join(SUPPORTED_PROVIDERS)}",
            )

        resolved_model = cls._resolve_model(provider_name, settings, model)
        common = dict(
            model=resolved_model,
            timeout=float(settings.llm_timeout),
            max_tokens=int(settings.llm_max_tokens),
            temperature=float(settings.llm_temperature),
        )

        if provider_name == "ollama":
            return OllamaProvider(base_url=settings.ollama_base_url, **common)
        if provider_name == "openai":
            return OpenAIProvider(api_key=settings.openai_api_key, **common)
        if provider_name == "gemini":
            return GeminiProvider(api_key=settings.gemini_api_key, **common)
        if provider_name == "groq":
            return GroqProvider(api_key=settings.groq_api_key, **common)
        if provider_name == "openrouter":
            return OpenRouterProvider(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                **common,
            )
        raise AIProviderUnavailable(provider_name, "Unknown provider")

    @classmethod
    def _resolve_model(
        cls,
        provider_name: str,
        settings: Settings,
        override: Optional[str],
    ) -> str:
        if override:
            return override
        if settings.llm_model:
            return settings.llm_model
        if provider_name == "ollama" and settings.ollama_model:
            return settings.ollama_model
        # Backward compat: OPENAI_MODEL when using openai
        if provider_name == "openai" and settings.openai_model:
            return settings.openai_model
        return DEFAULT_MODELS.get(provider_name, "qwen3:8b")

    @classmethod
    def fallback_chain(
        cls,
        *,
        primary: Optional[str] = None,
        settings: Optional[Settings] = None,
    ) -> list[str]:
        """Primary first, then configured fallbacks (deduped)."""
        settings = settings or get_settings()
        primary_name = (primary or settings.ai_provider or "ollama").strip().lower()

        # Local Ollama: do not auto-call OpenAI/Gemini unless explicitly enabled.
        if primary_name == "ollama" and not getattr(
            settings, "ai_enable_cloud_fallback", False
        ):
            logger.debug(
                "ai_cloud_fallback_disabled",
                provider="ollama",
                hint="Set AI_ENABLE_CLOUD_FALLBACK=true to allow cloud fallbacks",
            )
            return ["ollama"]

        raw = settings.ai_fallback_providers or "openai,gemini,openrouter,groq"
        fallbacks = [p.strip().lower() for p in raw.split(",") if p.strip()]
        ordered = [primary_name] + [p for p in fallbacks if p != primary_name]
        # Safety net for cloud environments (skip ollama unless primary)
        for p in ("openai", "gemini", "openrouter", "groq"):
            if p not in ordered:
                ordered.append(p)
        return [p for p in ordered if p in SUPPORTED_PROVIDERS]

    @classmethod
    def create_available_chain(
        cls,
        *,
        settings: Optional[Settings] = None,
        model: Optional[str] = None,
    ) -> list[AIProvider]:
        settings = settings or get_settings()
        providers: list[AIProvider] = []
        for name in cls.fallback_chain(settings=settings):
            try:
                provider = cls.create(name, settings=settings, model=model)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ai_provider_init_failed", provider=name, error=str(exc))
                continue
            if provider.is_available():
                providers.append(provider)
            else:
                logger.info("ai_provider_skipped_unavailable", provider=name)
        return providers

    @classmethod
    def describe_settings(cls, *, settings: Optional[Settings] = None) -> dict:
        """Non-secret snapshot for the AI settings UI."""
        settings = settings or get_settings()
        primary = (settings.ai_provider or "ollama").strip().lower()
        chain = cls.create_available_chain(settings=settings)
        active = chain[0] if chain else None
        return {
            "configured_provider": primary,
            "configured_model": cls._resolve_model(primary, settings, None),
            "active_provider": active.name if active else None,
            "active_model": active.model if active else None,
            "available": bool(active),
            "fallback_providers": cls.fallback_chain(settings=settings),
            "supported_providers": list(SUPPORTED_PROVIDERS),
            "ollama_base_url": settings.ollama_base_url,
            "ollama_model": settings.ollama_model,
        }
