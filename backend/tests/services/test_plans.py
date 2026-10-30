"""Plan limit unit tests for commercial launch pricing."""

import pytest
from fastapi import HTTPException

from app.services.plans import (
    assert_repo_limit,
    assert_scan_limit,
    assert_seat_limit,
    get_plan_limits,
    require_feature,
)


def test_free_limits():
    limits = get_plan_limits("free")
    assert limits.max_repositories == 1
    assert limits.max_users == 1
    assert limits.monthly_scan_limit == 20
    assert limits.upgrade_simulator is True
    assert limits.ai_enabled is False
    assert limits.ai_migration_assistant is False
    assert limits.display_name == "Evaluation Plan"


def test_starter_limits():
    limits = get_plan_limits("starter")
    assert limits.max_repositories == 10
    assert limits.max_users == 1
    assert limits.upgrade_simulator is True
    assert limits.ai_enabled is False
    assert limits.ai_migration_assistant is False
    assert limits.api_access is False
    assert limits.export_reports is True
    assert limits.display_name == "Starter"


def test_pro_limits():
    limits = get_plan_limits("pro")
    assert limits.ai_enabled is True
    assert limits.max_repositories is None
    assert limits.monthly_scan_limit is None
    assert limits.api_access is True
    assert limits.scheduled_scans is True
    assert limits.webhooks is True
    assert limits.ai_migration_assistant is False
    assert limits.upgrade_simulator is True


def test_team_has_migration_and_orgs():
    limits = get_plan_limits("team")
    assert limits.ai_migration_assistant is True
    assert limits.teams_enabled is True
    assert limits.rbac is True
    assert limits.audit_logs is True
    assert limits.max_users is None  # per-seat


def test_assert_repo_limit_blocks_free():
    with pytest.raises(HTTPException) as exc:
        assert_repo_limit("free", current_count=1, adding=1)
    assert exc.value.status_code == 402


def test_assert_repo_limit_starter():
    assert_repo_limit("starter", current_count=9, adding=1)
    with pytest.raises(HTTPException):
        assert_repo_limit("starter", current_count=10, adding=1)


def test_assert_seat_limit_starter():
    assert_seat_limit("starter", current_members=1, adding=0)
    with pytest.raises(HTTPException):
        assert_seat_limit("starter", current_members=1, adding=1)


def test_assert_seat_limit_team_unlimited():
    assert_seat_limit("team", current_members=50, adding=1)


def test_assert_scan_limit_free():
    assert_scan_limit("free", scans_this_month=19)
    with pytest.raises(HTTPException):
        assert_scan_limit("free", scans_this_month=20)


def test_require_feature_ai_and_migration():
    with pytest.raises(HTTPException):
        require_feature("free", feature="ai")
    with pytest.raises(HTTPException):
        require_feature("starter", feature="ai")
    require_feature("pro", feature="ai")
    with pytest.raises(HTTPException):
        require_feature("pro", feature="ai_migration_assistant")
    require_feature("team", feature="ai_migration_assistant")
    require_feature("free", feature="upgrade_simulator")
