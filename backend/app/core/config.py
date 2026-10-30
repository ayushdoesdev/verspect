"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import List
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})
_INTERNAL_HOSTS = _LOOPBACK_HOSTS | {
    "backend",
    "frontend",
    "postgres",
    "redis",
    "worker",
    "beat",
    "migrate",
}
_DEV_SMTP_HOSTS = _LOOPBACK_HOSTS | {"mailhog", "smtp"}


def _url_hostname(url: str) -> str:
    try:
        return (urlparse(url or "").hostname or "").lower()
    except ValueError:
        return ""


def _is_public_http_url(url: str) -> bool:
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"}:
        return False
    if not host or host in _INTERNAL_HOSTS:
        return False
    return True


def _redis_url_has_password(url: str) -> bool:
    try:
        return bool(urlparse(url or "").password)
    except ValueError:
        return False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Dependency Intelligence"
    app_env: str = "development"
    app_debug: bool = True
    app_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    secret_key: str = Field(default="change-me-to-a-long-random-secret-key-in-production")
    allowed_hosts: str = "localhost,127.0.0.1,backend,frontend"

    # Bootstrap platform admin (development / beta only — never used in production)
    bootstrap_admin_email: str = "admin@verspect.dev"
    bootstrap_admin_password: str = "Verspect@2026!"
    bootstrap_admin_name: str = "Verspect Admin"

    # Database
    database_url: str = (
        "postgresql+asyncpg://depintel:depintel_secret@localhost:5432/dependency_intelligence"
    )
    database_url_sync: str = (
        "postgresql://depintel:depintel_secret@localhost:5432/dependency_intelligence"
    )

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # GitHub OAuth
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/api/v1/auth/github/callback"
    github_webhook_secret: str = "change-me-webhook-secret"

    # AI / LLM (provider-agnostic — switch with AI_PROVIDER)
    # Local default: ollama. Production: gemini | openai | openrouter | groq
    ai_provider: str = "ollama"  # ollama | openai | gemini | groq | openrouter
    ai_fallback_providers: str = "openai,gemini,openrouter,groq"
    # When AI_PROVIDER=ollama, cloud fallbacks are OFF unless explicitly enabled.
    ai_enable_cloud_fallback: bool = False
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"  # legacy alias for llm_model
    gemini_api_key: str = ""
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    llm_model: str = ""  # empty → provider default / ollama_model / openai_model
    llm_timeout: float = 180.0
    llm_max_tokens: int = 4096
    # Smaller cap for scan-time dependency summaries (faster local inference).
    llm_summary_max_tokens: int = 512
    llm_temperature: float = 0.2
    ai_cache_ttl_seconds: int = 60 * 60 * 24  # 24h

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    # Billing — active gateway (stripe | razorpay). App code uses BillingProvider only.
    billing_provider: str = "stripe"

    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_starter_monthly: str = ""
    stripe_price_starter_yearly: str = ""
    stripe_price_pro_monthly: str = ""
    stripe_price_pro_yearly: str = ""
    stripe_price_team_monthly: str = ""
    stripe_price_team_yearly: str = ""

    # Razorpay
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpay_plan_starter_monthly: str = ""
    razorpay_plan_starter_yearly: str = ""
    razorpay_plan_pro_monthly: str = ""
    razorpay_plan_pro_yearly: str = ""
    razorpay_plan_team_monthly: str = ""
    razorpay_plan_team_yearly: str = ""

    # Notifications
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@dependency-intelligence.local"
    smtp_tls: bool = False
    slack_webhook_url: str = ""

    # License policy
    license_policy_reject: str = "GPL-2.0,GPL-3.0,AGPL-3.0,AGPL-1.0"
    license_policy_warn: str = "LGPL-2.1,LGPL-3.0"

    # Scanner
    scan_clone_dir: str = "/tmp/depintel/repos"
    scan_max_file_size_mb: int = 5
    scan_concurrency: int = 4

    # Background jobs / worker lifecycle (never hardcode these in tasks or API)
    # How long a job may sit queued before we consider the worker unavailable.
    scan_pickup_timeout_seconds: int = 60
    # Hard ceiling for a running scan before it is reaped as timed out.
    scan_running_timeout_minutes: int = 30
    # How often a running worker refreshes `last_heartbeat_at`.
    worker_heartbeat_seconds: int = 15
    # Missing heartbeats for this long ⇒ job is considered stale/dead.
    stale_scan_timeout_minutes: int = 5
    # Celery execution guards for the scan pipeline.
    scan_soft_time_limit_seconds: int = 1800
    scan_hard_time_limit_seconds: int = 2100
    # Upgrade Simulator equivalents.
    simulation_pickup_timeout_seconds: int = 60
    simulation_running_timeout_minutes: int = 15
    simulation_soft_time_limit_seconds: int = 900
    simulation_hard_time_limit_seconds: int = 1080
    # Queue is considered blocked when this many jobs wait with no worker progress.
    queue_blocked_depth_threshold: int = 25
    # Celery `inspect` is a blocking broadcast; keep the wait short and cache the
    # verdict so job-status polling stays cheap.
    worker_health_probe_timeout_seconds: float = 0.75
    worker_health_cache_seconds: float = 10.0
    # Automatic retries performed by the reaper for transient failures.
    job_max_auto_retries: int = 2

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    @field_validator("secret_key")
    @classmethod
    def secret_key_strength(cls, value: str) -> str:
        if len(value) < 16:
            raise ValueError("SECRET_KEY must be at least 16 characters")
        return value

    @model_validator(mode="after")
    def reject_insecure_production_defaults(self) -> "Settings":
        if not self.is_production:
            return self
        if self.app_debug:
            raise ValueError("APP_DEBUG must be false in production")
        default_secret = "change-me-to-a-long-random-secret-key-in-production"
        if self.secret_key == default_secret or self.secret_key.startswith("change-me"):
            raise ValueError("SECRET_KEY must be a unique value in production")
        default_hook = "change-me-webhook-secret"
        if not self.github_webhook_secret or self.github_webhook_secret in {default_hook} or self.github_webhook_secret.startswith("change-me"):
            raise ValueError("GITHUB_WEBHOOK_SECRET must be set in production")
        db_blob = f"{self.database_url} {self.database_url_sync}".lower()
        if "depintel_secret" in db_blob:
            raise ValueError(
                "DATABASE_URL must not use the development password in production"
            )
        if not _is_public_http_url(self.app_url):
            raise ValueError(
                "APP_URL must be the public frontend origin in production, not localhost"
            )
        if not _is_public_http_url(self.api_url):
            raise ValueError(
                "API_URL must be the public API origin in production, not localhost"
            )
        if not (self.github_client_id or "").strip() or not (self.github_client_secret or "").strip():
            raise ValueError(
                "GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET must be set in production"
            )
        if not _is_public_http_url(self.github_redirect_uri):
            raise ValueError(
                "GITHUB_REDIRECT_URI must be the public API callback in production, not localhost"
            )
        smtp_host = (self.smtp_host or "").strip().lower()
        if smtp_host in _DEV_SMTP_HOSTS:
            raise ValueError(
                "SMTP_HOST must be a real mail server in production, not localhost or Mailhog"
            )
        for label, url in (
            ("REDIS_URL", self.redis_url),
            ("CELERY_BROKER_URL", self.celery_broker_url),
            ("CELERY_RESULT_BACKEND", self.celery_result_backend),
        ):
            if not _redis_url_has_password(url):
                raise ValueError(f"{label} must include a password in production")
        api_host = _url_hostname(self.api_url)
        allowed = {h.lower() for h in self.allowed_hosts_list}
        if api_host and api_host not in allowed:
            raise ValueError(
                "ALLOWED_HOSTS must include the API_URL hostname in production"
            )
        provider = (self.ai_provider or "").strip().lower()
        provider_keys = {
            "openai": self.openai_api_key,
            "gemini": self.gemini_api_key,
            "groq": self.groq_api_key,
            "openrouter": self.openrouter_api_key,
        }
        if provider in provider_keys and not (provider_keys[provider] or "").strip():
            raise ValueError(
                f"AI_PROVIDER={provider} requires the corresponding API key in production"
            )
        return self

    @property
    def allowed_hosts_list(self) -> List[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @property
    def license_reject_list(self) -> List[str]:
        return [x.strip().upper() for x in self.license_policy_reject.split(",") if x.strip()]

    @property
    def license_warn_list(self) -> List[str]:
        return [x.strip().upper() for x in self.license_policy_warn.split(",") if x.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def cors_origins(self) -> List[str]:
        origins = [self.app_url]
        if not self.is_production:
            origins.extend(["http://localhost:3000", "http://127.0.0.1:3000"])
        unique: list[str] = []
        for origin in origins:
            cleaned = (origin or "").rstrip("/")
            if cleaned and cleaned not in unique:
                unique.append(cleaned)
        return unique


@lru_cache
def get_settings() -> Settings:
    return Settings()
