"""Unit tests for Team+ AI Migration Assistant merge helpers."""

from __future__ import annotations

from app.migration_engine.ai_patch_assistant import merge_assistant_with_deterministic


def test_merge_enriches_without_overriding_status():
    deterministic = [
        {
            "file_path": "user.py",
            "line": 10,
            "symbol": "validator",
            "current_code": "@validator",
            "suggested_code": "@field_validator",
            "migration_status": "automatic_migration",
            "status_title": "Automatic migration available",
            "automatic": True,
            "explanation": "deterministic",
        }
    ]
    ai = [
        {
            "file_path": "user.py",
            "line": 10,
            "symbol": "validator",
            "current_code": '@validator("name")',
            "suggested_code": '@field_validator("name")',
            "ai_suggested_code": '@field_validator("name")',
            "ai_explanation": "ai guidance",
            "migration_status": "automatic_migration",
            "explanation": "ai",
            "source": "ai_migration_assistant",
        }
    ]
    merged = merge_assistant_with_deterministic(deterministic, ai)
    assert len(merged) == 1
    assert merged[0]["migration_status"] == "automatic_migration"
    assert merged[0]["suggested_code"] == "@field_validator"  # deterministic patch kept
    assert merged[0]["ai_suggested_code"] == '@field_validator("name")'
    assert merged[0]["ai_explanation"] == "ai guidance"
    assert merged[0]["source"] == "ai_migration_assistant+deterministic"


def test_merge_keeps_deterministic_when_ai_empty():
    deterministic = [
        {
            "file_path": "user.py",
            "line": 1,
            "symbol": "BaseModel",
            "migration_status": "no_migration_required",
            "current_code": "class User(BaseModel):",
            "suggested_code": None,
        }
    ]
    assert merge_assistant_with_deterministic(deterministic, []) == deterministic


def test_merge_does_not_add_ai_only_sites():
    deterministic = [
        {
            "file_path": "a.py",
            "line": 1,
            "symbol": "x",
            "migration_status": "unknown",
            "suggested_code": None,
        }
    ]
    ai = [
        {
            "file_path": "new.py",
            "line": 9,
            "symbol": "invented",
            "migration_status": "automatic_migration",
            "suggested_code": "y()",
            "ai_suggested_code": "y()",
        }
    ]
    merged = merge_assistant_with_deterministic(deterministic, ai)
    assert len(merged) == 1
    assert merged[0]["symbol"] == "x"
