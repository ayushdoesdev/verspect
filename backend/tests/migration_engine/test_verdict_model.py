"""Deterministic Upgrade Simulator verdict rules."""

from __future__ import annotations

from app.migration_engine.ai_patch_assistant import merge_assistant_with_deterministic
from app.migration_engine.patch_generator import PatchGenerator
from app.migration_engine.rule_catalog import rules_for_upgrade
from app.migration_engine.rule_matcher import RuleMatcher
from app.migration_engine.semantic_index import SemanticASTIndex
from app.scanners.ast_parser import ASTParser
from app.services.upgrade_helpers import (
    MIGRATION_STATUS_AUTOMATIC,
    MIGRATION_STATUS_MANUAL,
    MIGRATION_STATUS_NO_CHANGE,
    MIGRATION_STATUS_UNKNOWN,
    STATUS_TITLE,
)


def test_no_knowledge_is_unknown_not_no_changes(tmp_path):
    (tmp_path / "m.py").write_text(
        "import obscurpkg as o\nx = o.thing()\n",
        encoding="utf-8",
    )
    usages = [
        u.to_dict()
        for u in ASTParser(tmp_path, known_packages={"obscurpkg"}).scan().usages
    ]
    rules = rules_for_upgrade("obscurpkg", "1.0.0", "2.0.0")
    assert rules == []

    unmatched = PatchGenerator().classify_unmatched_usages(
        usages, [], knowledge_available=False
    )
    assert unmatched
    assert all(f.status == MIGRATION_STATUS_UNKNOWN for f in unmatched)
    assert all("No changes" not in (f.reason or "") for f in unmatched)


def test_knowledge_without_match_is_no_changes(tmp_path):
    (tmp_path / "m.py").write_text(
        "from pydantic import BaseModel\nclass U(BaseModel):\n    x: int\n",
        encoding="utf-8",
    )
    usages = [
        u.to_dict()
        for u in ASTParser(tmp_path, known_packages={"pydantic"}).scan().usages
    ]
    rules = rules_for_upgrade("pydantic", "1.10.0", "2.5.0")
    assert rules
    index = SemanticASTIndex.from_usage_dicts(usages).filter_package("pydantic")
    matches = RuleMatcher().match_index(index, rules)
    # BaseModel matches as unchanged — remaining unmatched (if any) are no-change
    unmatched = PatchGenerator().classify_unmatched_usages(
        index.to_usage_dicts(), matches, knowledge_available=True
    )
    assert all(f.status == MIGRATION_STATUS_NO_CHANGE for f in unmatched)


def test_matched_alias_is_automatic(tmp_path):
    (tmp_path / "m.py").write_text(
        "import numpy as np\narr = np.array([1], dtype=np.float)\n",
        encoding="utf-8",
    )
    usages = [
        u.to_dict()
        for u in ASTParser(tmp_path, known_packages={"numpy"}).scan().usages
    ]
    rules = rules_for_upgrade("numpy", "1.26.4", "2.0.0")
    matches = RuleMatcher().match(
        rules, SemanticASTIndex.from_usage_dicts(usages).filter_package("numpy")
    )
    _, findings = PatchGenerator().generate(matches)
    auto = [f for f in findings if f.status == MIGRATION_STATUS_AUTOMATIC]
    assert auto
    assert any((f.replacement or "") == "float" for f in auto)


def test_ai_merge_never_overrides_deterministic_status():
    deterministic = [
        {
            "file_path": "a.py",
            "line": 1,
            "symbol": "float",
            "migration_status": MIGRATION_STATUS_UNKNOWN,
            "status_title": STATUS_TITLE[MIGRATION_STATUS_UNKNOWN],
            "current_code": "np.float",
            "suggested_code": None,
            "automatic": False,
            "explanation": "Unknown",
        },
        {
            "file_path": "b.py",
            "line": 2,
            "symbol": "validator",
            "migration_status": MIGRATION_STATUS_MANUAL,
            "status_title": STATUS_TITLE[MIGRATION_STATUS_MANUAL],
            "current_code": "@validator",
            "suggested_code": None,
            "automatic": False,
        },
    ]
    ai = [
        {
            "file_path": "a.py",
            "line": 1,
            "symbol": "float",
            "migration_status": MIGRATION_STATUS_AUTOMATIC,
            "suggested_code": "float",
            "current_code": "np.float",
            "ai_suggested_code": "float",
            "ai_explanation": "use builtin float",
            "explanation": "use builtin float",
            "source": "ai_migration_assistant",
        },
        {
            "file_path": "b.py",
            "line": 2,
            "symbol": "validator",
            "migration_status": MIGRATION_STATUS_AUTOMATIC,
            "suggested_code": "@field_validator",
            "current_code": "@validator",
            "ai_suggested_code": "@field_validator",
            "ai_explanation": "rename",
            "source": "ai_migration_assistant",
        },
    ]
    merged = merge_assistant_with_deterministic(deterministic, ai)
    by_sym = {m["symbol"]: m for m in merged}
    assert by_sym["float"]["migration_status"] == MIGRATION_STATUS_UNKNOWN
    assert by_sym["float"]["suggested_code"] is None
    assert by_sym["float"]["ai_suggested_code"] == "float"
    assert by_sym["validator"]["migration_status"] == MIGRATION_STATUS_MANUAL
    assert by_sym["validator"]["suggested_code"] is None
    assert by_sym["validator"]["ai_suggested_code"] == "@field_validator"
