"""GitHub OAuth and API client service."""

import secrets
from typing import Any, Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.mixins import utcnow
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decrypt_token,
    encrypt_token,
)
from app.models.user import User
from app.schemas.user import TokenResponse, UserResponse

logger = get_logger(__name__)
settings = get_settings()

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_BASE = "https://api.github.com"
GITHUB_SCOPES = "read:user user:email repo"


class GitHubAuthRequired(Exception):
    """Stored GitHub token is missing, revoked, or rejected by GitHub (401)."""

    def __init__(self, message: str = "Reconnect GitHub") -> None:
        super().__init__(message)


class GitHubRateLimited(Exception):
    """GitHub 429 / secondary rate limit."""

    def __init__(self, retry_after: Optional[int] = None) -> None:
        self.retry_after = retry_after
        super().__init__("GitHub rate limit exceeded. Try again shortly.")


class GitHubPermissionDenied(Exception):
    """Token lacks permission for the requested GitHub operation."""

    def __init__(self, message: str = "GitHub permission denied") -> None:
        super().__init__(message)


def _ensure_github_ok(response: httpx.Response) -> None:
    """Map GitHub auth / rate-limit failures to typed errors; never log tokens."""
    if response.status_code == 401:
        raise GitHubAuthRequired("Reconnect GitHub")
    if response.status_code == 429:
        retry = response.headers.get("Retry-After")
        raise GitHubRateLimited(int(retry) if retry and str(retry).isdigit() else None)
    if response.status_code == 403:
        remaining = response.headers.get("X-RateLimit-Remaining")
        body = (response.text or "").lower()
        if remaining == "0" or "rate limit" in body:
            retry = response.headers.get("Retry-After") or response.headers.get("X-RateLimit-Reset")
            raise GitHubRateLimited(int(retry) if retry and str(retry).isdigit() else None)
        raise GitHubPermissionDenied(
            "GitHub denied this action. Reconnect GitHub with the repo scope, or check repository permissions."
        )
    response.raise_for_status()


class GitHubAuthService:
    def __init__(self) -> None:
        self.client_id = settings.github_client_id
        self.client_secret = settings.github_client_secret
        self.redirect_uri = settings.github_redirect_uri

    def get_authorization_url(self, state: Optional[str] = None) -> tuple[str, str]:
        state = state or secrets.token_urlsafe(32)
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": GITHUB_SCOPES,
            "state": state,
            "allow_signup": "true",
        }
        query = "&".join(f"{k}={httpx.QueryParams({k: v})[k]}" for k, v in params.items())
        return f"{GITHUB_AUTHORIZE_URL}?{query}", state

    async def exchange_code(self, code: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GITHUB_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
            )
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                raise ValueError(data.get("error_description", data["error"]))
            return data

    async def fetch_github_user(self, access_token: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            user_resp = await client.get(f"{GITHUB_API_BASE}/user", headers=headers)
            user_resp.raise_for_status()
            user_data = user_resp.json()

            email = user_data.get("email")
            if not email:
                emails_resp = await client.get(f"{GITHUB_API_BASE}/user/emails", headers=headers)
                if emails_resp.status_code == 200:
                    emails = emails_resp.json()
                    primary = next(
                        (e for e in emails if e.get("primary") and e.get("verified")),
                        None,
                    )
                    if primary:
                        email = primary["email"]
                    elif emails:
                        email = emails[0]["email"]
            user_data["email"] = email
            return user_data

    async def upsert_user(
        self,
        db: AsyncSession,
        github_user: dict[str, Any],
        access_token: str,
        scopes: Optional[str] = None,
    ) -> User:
        result = await db.execute(
            select(User).where(User.github_id == github_user["id"])
        )
        user = result.scalar_one_or_none()

        encrypted = encrypt_token(access_token)
        if user is None:
            user = User(
                github_id=github_user["id"],
                github_login=github_user["login"],
                email=github_user.get("email"),
                name=github_user.get("name"),
                avatar_url=github_user.get("avatar_url"),
                github_access_token_encrypted=encrypted,
                github_token_scopes=scopes,
                last_login_at=utcnow(),
            )
            db.add(user)
            logger.info("user_created", github_login=user.github_login)
        else:
            user.github_login = github_user["login"]
            user.email = github_user.get("email") or user.email
            user.name = github_user.get("name") or user.name
            user.avatar_url = github_user.get("avatar_url") or user.avatar_url
            user.github_access_token_encrypted = encrypted
            user.github_token_scopes = scopes or user.github_token_scopes
            user.last_login_at = utcnow()
            user.is_active = True
            logger.info("user_logged_in", github_login=user.github_login)

        await db.flush()
        from app.services.organizations import ensure_personal_organization

        await ensure_personal_organization(db, user)
        user.auth_provider = user.auth_provider or "github"
        if github_user.get("email"):
            user.email_verified = True
        await db.flush()
        await db.refresh(user)
        return user

    def build_token_response(self, user: User) -> TokenResponse:
        access = create_access_token(
            user.id,
            extra_claims={"login": user.github_login},
        )
        refresh = create_refresh_token(user.id)
        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
            user=UserResponse.model_validate(user),
        )

    async def authenticate_with_code(
        self,
        db: AsyncSession,
        code: str,
    ) -> TokenResponse:
        token_data = await self.exchange_code(code)
        access_token = token_data["access_token"]
        scopes = token_data.get("scope")
        github_user = await self.fetch_github_user(access_token)
        user = await self.upsert_user(db, github_user, access_token, scopes)
        return self.build_token_response(user)

    @staticmethod
    def get_user_github_token(user: User) -> str:
        if not user.github_access_token_encrypted:
            raise GitHubAuthRequired("Reconnect GitHub")
        try:
            return decrypt_token(user.github_access_token_encrypted)
        except ValueError as exc:
            raise GitHubAuthRequired("Reconnect GitHub") from exc


class GitHubAPIClient:
    """Authenticated GitHub REST API client for a user."""

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "DependencyIntelligence/1.0",
        }

    async def list_repositories(
        self,
        page: int = 1,
        per_page: int = 100,
        affiliation: str = "owner,collaborator,organization_member",
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/user/repos",
                headers=self.headers,
                params={
                    "page": page,
                    "per_page": per_page,
                    "affiliation": affiliation,
                    "sort": "updated",
                    "direction": "desc",
                },
            )
            _ensure_github_ok(response)
            return response.json()

    async def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}",
                headers=self.headers,
            )
            _ensure_github_ok(response)
            return response.json()

    async def create_webhook(
        self,
        owner: str,
        repo: str,
        webhook_url: str,
        secret: str,
    ) -> dict[str, Any]:
        payload = {
            "name": "web",
            "active": True,
            "events": ["push", "release", "repository"],
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "secret": secret,
                "insecure_ssl": "0",
            },
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/hooks",
                headers=self.headers,
                json=payload,
            )
            if response.status_code == 422:
                # Hook may already exist — list and reuse
                existing = await client.get(
                    f"{GITHUB_API_BASE}/repos/{owner}/{repo}/hooks",
                    headers=self.headers,
                )
                _ensure_github_ok(existing)
                for hook in existing.json():
                    if hook.get("config", {}).get("url") == webhook_url:
                        return hook
            _ensure_github_ok(response)
            return response.json()

    async def delete_webhook(self, owner: str, repo: str, hook_id: int) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/hooks/{hook_id}",
                headers=self.headers,
            )
            if response.status_code not in (204, 404):
                _ensure_github_ok(response)

    async def get_default_branch_sha(self, owner: str, repo: str, branch: str) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{branch}",
                headers=self.headers,
            )
            _ensure_github_ok(response)
            return response.json()["sha"]

    async def create_branch(
        self, owner: str, repo: str, *, branch: str, from_sha: str
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/refs",
                headers=self.headers,
                json={"ref": f"refs/heads/{branch}", "sha": from_sha},
            )
            if response.status_code == 422:
                # Branch may already exist — reuse it.
                existing = await client.get(
                    f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/ref/heads/{branch}",
                    headers=self.headers,
                )
                _ensure_github_ok(existing)
                return existing.json()
            _ensure_github_ok(response)
            return response.json()

    async def get_file_contents(
        self, owner: str, repo: str, path: str, *, ref: str
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}",
                headers=self.headers,
                params={"ref": ref},
            )
            _ensure_github_ok(response)
            return response.json()

    async def put_file(
        self,
        owner: str,
        repo: str,
        path: str,
        *,
        message: str,
        content_b64: str,
        branch: str,
        sha: Optional[str] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "message": message,
            "content": content_b64,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.put(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}",
                headers=self.headers,
                json=payload,
            )
            _ensure_github_ok(response)
            return response.json()

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        *,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls",
                headers=self.headers,
                json={"title": title, "body": body, "head": head, "base": base},
            )
            _ensure_github_ok(response)
            return response.json()


github_auth_service = GitHubAuthService()
