"""Organization license policy helpers (deterministic, metadata-based)."""

from __future__ import annotations

from typing import Any, Optional

from app.core.config import get_settings
from app.core.enums import LicensePolicyAction


def normalize_license_list(items: Optional[list[str] | list[Any]]) -> list[str]:
    if not items:
        return []
    out: list[str] = []
    for item in items:
        if item is None:
            continue
        s = str(item).strip()
        if s:
            out.append(s)
    return out


def license_policy_from_org_settings(
    settings: Optional[dict[str, Any]],
) -> tuple[Optional[list[str]], Optional[list[str]]]:
    """
    Read org.settings.license_policy.

    Returns (reject_list, warn_list). None means fall back to global env defaults.
    Empty list means explicitly no items in that bucket.
    """
    if not settings or not isinstance(settings, dict):
        return None, None
    policy = settings.get("license_policy")
    if not isinstance(policy, dict):
        return None, None
    reject = policy.get("reject")
    warn = policy.get("warn")
    reject_list = normalize_license_list(reject) if reject is not None else None
    warn_list = normalize_license_list(warn) if warn is not None else None
    return reject_list, warn_list


def resolve_license_policy_lists(
    org_settings: Optional[dict[str, Any]] = None,
) -> tuple[list[str], list[str]]:
    """Merge org policy with global defaults when org lists are unset."""
    global_settings = get_settings()
    reject_override, warn_override = license_policy_from_org_settings(org_settings)
    reject = (
        reject_override
        if reject_override is not None
        else list(global_settings.license_reject_list)
    )
    warn = (
        warn_override
        if warn_override is not None
        else list(global_settings.license_warn_list)
    )
    return reject, warn


def license_score_for_action(action: Optional[str]) -> float:
    """Transparent 0–100 license risk component for health breakdown UI."""
    if action == LicensePolicyAction.ALLOW.value:
        return 100.0
    if action == LicensePolicyAction.WARN.value:
        return 60.0
    if action == LicensePolicyAction.REJECT.value:
        return 15.0
    return 50.0


def public_license_policy(org_settings: Optional[dict[str, Any]]) -> dict[str, Any]:
    reject, warn = resolve_license_policy_lists(org_settings)
    return {
        "reject": reject,
        "warn": warn,
        "source": (
            "organization"
            if org_settings
            and isinstance(org_settings.get("license_policy"), dict)
            else "global_default"
        ),
    }
