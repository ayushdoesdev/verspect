"""GitHub client error mapping."""

from app.services.github import GitHubAuthRequired, GitHubPermissionDenied, GitHubRateLimited, _ensure_github_ok


class _Resp:
    def __init__(self, status_code: int, headers: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


def test_401_maps_to_auth_required() -> None:
    try:
        _ensure_github_ok(_Resp(401))
        raise AssertionError("expected GitHubAuthRequired")
    except GitHubAuthRequired:
        pass


def test_429_maps_to_rate_limited() -> None:
    try:
        _ensure_github_ok(_Resp(429, {"Retry-After": "12"}))
        raise AssertionError("expected GitHubRateLimited")
    except GitHubRateLimited as exc:
        assert exc.retry_after == 12


def test_403_rate_limit_header() -> None:
    try:
        _ensure_github_ok(_Resp(403, {"X-RateLimit-Remaining": "0"}))
        raise AssertionError("expected GitHubRateLimited")
    except GitHubRateLimited:
        pass


def test_403_permission_denied() -> None:
    try:
        _ensure_github_ok(_Resp(403, text="resource not accessible"))
        raise AssertionError("expected GitHubPermissionDenied")
    except GitHubPermissionDenied:
        pass
