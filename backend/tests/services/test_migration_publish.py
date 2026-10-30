"""Migration publish helpers — snippet apply and patch selection."""

from app.services.migration_publish import apply_snippet, selectable_patches


def test_apply_snippet_replaces_first_occurrence() -> None:
    original = "from pydantic import validator\n\nclass M:\n    pass\n"
    updated = apply_snippet(original, "from pydantic import validator", "from pydantic import field_validator")
    assert updated is not None
    assert "field_validator" in updated
    assert "import validator\n" not in updated


def test_apply_snippet_returns_none_when_missing() -> None:
    assert apply_snippet("print(1)\n", "missing", "x") is None


def test_selectable_patches_requires_automatic_validated() -> None:
    rows = [
        {
            "file_path": "src/a.py",
            "current_code": "old()",
            "suggested_code": "new()",
            "migration_status": "automatic_migration",
            "automatic": True,
        },
        {
            "file_path": "src/b.py",
            "current_code": "old()",
            "suggested_code": "new()",
            "migration_status": "manual_review_required",
            "automatic": False,
        },
        {
            "file_path": "(repository)",
            "current_code": "x",
            "suggested_code": "y",
            "migration_status": "automatic_migration",
            "automatic": True,
        },
    ]
    selected = selectable_patches(rows)
    assert len(selected) == 1
    assert selected[0]["file_path"] == "src/a.py"


def test_confirm_required_message() -> None:
    import inspect

    from app.services.migration_publish import publish_migration_pull_request

    src = inspect.getsource(publish_migration_pull_request)
    assert "confirm" in src
    assert "Explicit confirmation" in src
