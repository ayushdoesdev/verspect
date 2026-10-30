"""AI layer exceptions — never crash the app on provider failure."""

from __future__ import annotations


class AIError(Exception):
    """Base AI layer error."""


class AIProviderError(AIError):
    """A specific provider failed to complete a request."""

    def __init__(self, provider: str, message: str, *, cause: Exception | None = None) -> None:
        self.provider = provider
        self.cause = cause
        super().__init__(f"[{provider}] {message}")


class AIProviderUnavailable(AIProviderError):
    """Provider is not configured or not reachable."""


class AITimeoutError(AIProviderError):
    """Provider did not finish within the configured timeout."""


class AIRateLimitError(AIProviderError):
    """Provider rejected the request due to quota or rate limits."""


class AIValidationError(AIError):
    """Structured output failed Pydantic validation."""

    def __init__(self, message: str, *, raw: object | None = None) -> None:
        self.raw = raw
        super().__init__(message)


class AIAllProvidersFailed(AIError):
    """Every configured provider (primary + fallbacks) failed."""

    def __init__(self, errors: list[str], *, cause: Exception | None = None) -> None:
        self.errors = errors
        self.cause = cause
        joined = "; ".join(errors) if errors else "no providers available"
        super().__init__(f"All AI providers failed: {joined}")


def classify_ai_failure(exc: BaseException | None) -> str:
    """Map a provider exception to a non-secret intelligence degradation key."""
    if exc is None:
        return "ai_completion_failed"
    if isinstance(exc, AITimeoutError):
        return "ai_timeout"
    if isinstance(exc, AIRateLimitError):
        return "ai_rate_limited"
    if isinstance(exc, AIProviderUnavailable):
        return "ai_unavailable"
    if isinstance(exc, AIValidationError):
        return "malformed_ai_response"
    name = type(exc).__name__.lower()
    blob = f"{name} {exc}".lower()
    if "timeout" in name or "timed out" in blob or "timeout" in blob:
        return "ai_timeout"
    if "429" in blob or "rate limit" in blob or "quota" in blob or "insufficient_quota" in blob:
        return "ai_rate_limited"
    if "connect" in blob or "unreachable" in blob or "unavailable" in blob:
        return "ai_unavailable"
    return "ai_completion_failed"
