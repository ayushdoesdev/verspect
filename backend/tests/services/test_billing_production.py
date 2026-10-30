"""Production billing must not grant paid plans without credentials."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.billing.base import BillingNotConfigured
from app.services.billing.stripe_provider import StripeProvider

# Minimal unique production config — never copy development placeholders.
_PROD = dict(
    app_env="production",
    app_debug=False,
    secret_key="x" * 16,
    github_webhook_secret="unique-webhook-secret",
    github_client_id="github-oauth-client-id",
    github_client_secret="github-oauth-client-secret",
    github_redirect_uri="https://api.example.com/api/v1/auth/github/callback",
    database_url="postgresql+asyncpg://app:strong-db-pass@db:5432/app",
    database_url_sync="postgresql://app:strong-db-pass@db:5432/app",
    app_url="https://app.example.com",
    api_url="https://api.example.com",
    allowed_hosts="api.example.com,localhost,backend",
    redis_url="redis://:redis-prod-pass@redis:6379/0",
    celery_broker_url="redis://:redis-prod-pass@redis:6379/1",
    celery_result_backend="redis://:redis-prod-pass@redis:6379/2",
    smtp_host="smtp.example.com",
    smtp_port=587,
    ai_provider="ollama",
)


def test_production_checkout_without_keys_raises(monkeypatch) -> None:
    provider = StripeProvider()
    monkeypatch.setattr(provider, "_client", lambda: None)
    monkeypatch.setattr(provider, "_price_map", lambda: {})

    async def fake_customer(*_a, **_k) -> str:
        return "cus_x"

    monkeypatch.setattr(provider, "create_customer", fake_customer)

    class _Org:
        id = uuid4()
        name = "Acme"
        slug = "acme"
        billing_customer_id = "cus_x"
        stripe_customer_id = "cus_x"

    import app.services.billing.stripe_provider as mod

    monkeypatch.setattr(mod, "settings", SimpleNamespace(is_production=True))

    async def _run() -> None:
        try:
            await provider.create_checkout_session(
                None,  # type: ignore[arg-type]
                org=_Org(),  # type: ignore[arg-type]
                plan="starter",
                interval="month",
                success_url="http://x/ok",
                cancel_url="http://x/cancel",
                customer_email="a@b.c",
            )
            raise AssertionError("expected BillingNotConfigured")
        except BillingNotConfigured:
            pass

    asyncio.run(_run())


def test_settings_is_production() -> None:
    s = Settings(**_PROD)
    assert s.is_production is True
    assert "localhost:3000" not in s.cors_origins
    assert s.app_url in s.cors_origins
    prod_alias = Settings(**{**_PROD, "app_env": "prod"})
    assert prod_alias.is_production is True
    d = Settings(app_env="development", secret_key="x" * 16)
    assert d.is_production is False
    assert "http://localhost:3000" in d.cors_origins


def test_production_rejects_localhost_urls_and_empty_github() -> None:
    with pytest.raises(ValidationError):
        Settings(**{**_PROD, "app_url": "http://localhost:3000"})
    with pytest.raises(ValidationError):
        Settings(**{**_PROD, "api_url": "http://127.0.0.1:8000"})
    with pytest.raises(ValidationError):
        Settings(**{**_PROD, "github_client_id": "", "github_client_secret": ""})
    with pytest.raises(ValidationError):
        Settings(
            **{
                **_PROD,
                "github_redirect_uri": "http://localhost:8000/api/v1/auth/github/callback",
            }
        )


def test_production_rejects_mailhog_and_unauthenticated_redis() -> None:
    with pytest.raises(ValidationError):
        Settings(**{**_PROD, "smtp_host": "mailhog"})
    with pytest.raises(ValidationError):
        Settings(**{**_PROD, "smtp_host": "localhost"})
    with pytest.raises(ValidationError):
        Settings(**{**_PROD, "redis_url": "redis://redis:6379/0"})
    with pytest.raises(ValidationError):
        Settings(**{**_PROD, "allowed_hosts": "localhost,backend,frontend"})
    with pytest.raises(ValidationError):
        Settings(**{**_PROD, "ai_provider": "openai", "openai_api_key": ""})
    ok = Settings(**{**_PROD, "ai_provider": "openai", "openai_api_key": "sk-test"})
    assert ok.ai_provider == "openai"


def test_production_rejects_default_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            app_debug=False,
            secret_key="change-me-to-a-long-random-secret-key-in-production",
            github_webhook_secret="unique-webhook-secret",
            database_url="postgresql+asyncpg://app:strong-db-pass@db:5432/app",
            database_url_sync="postgresql://app:strong-db-pass@db:5432/app",
        )


def test_production_rejects_debug_and_default_database_password() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            app_debug=True,
            secret_key="x" * 16,
            github_webhook_secret="unique-webhook-secret",
            database_url="postgresql+asyncpg://app:strong-db-pass@db:5432/app",
            database_url_sync="postgresql://app:strong-db-pass@db:5432/app",
        )
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            app_debug=False,
            secret_key="x" * 16,
            github_webhook_secret="unique-webhook-secret",
        )
