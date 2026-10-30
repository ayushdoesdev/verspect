"""License policy resolution tests."""

from __future__ import annotations

from app.scanners.license import evaluate_license_policy
from app.services.license_policy import (
    license_policy_from_org_settings,
    public_license_policy,
    resolve_license_policy_lists,
)


def test_empty_org_reject_list_is_not_replaced_by_defaults() -> None:
    reject, warn = license_policy_from_org_settings(
        {"license_policy": {"reject": [], "warn": ["LGPL-3.0"]}}
    )
    assert reject == []
    assert warn == ["LGPL-3.0"]
    action = evaluate_license_policy("GPL-3.0", reject_list=reject, warn_list=warn)
    # Explicit empty reject → GPL allowed (unless in warn)
    assert action == "allow"


def test_missing_org_policy_uses_global_defaults() -> None:
    reject, warn = resolve_license_policy_lists(None)
    assert "GPL-3.0" in [x.upper() for x in reject] or any("GPL" in x.upper() for x in reject)
    assert isinstance(warn, list)
    policy = public_license_policy(None)
    assert policy["source"] == "global_default"


def test_org_policy_source_marked_organization() -> None:
    policy = public_license_policy(
        {"license_policy": {"reject": ["AGPL-3.0"], "warn": []}}
    )
    assert policy["source"] == "organization"
    assert policy["reject"] == ["AGPL-3.0"]
