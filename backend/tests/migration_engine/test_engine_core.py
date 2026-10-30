"""Unit tests for Universal Migration Intelligence Engine."""

from __future__ import annotations

from app.migration_engine.models import MigrationRuleDTO
from app.migration_engine.rule_generator import RuleGenerator
from app.migration_engine.rule_matcher import RuleMatcher
from app.migration_engine.rule_validator import RuleValidator
from app.migration_engine.release_fetcher import version_in_range


class _StubAI:
    available = False


def test_rule_matcher_exact_and_leaf():
    matcher = RuleMatcher()
    rules = [
        MigrationRuleDTO(
            library="acme",
            from_version="1.0",
            to_version="2.0",
            symbol="acme.core.OldAPI",
            kind="removed",
            description="OldAPI removed",
            confidence=0.9,
            official_reference="https://example.com/changelog",
        ),
        MigrationRuleDTO(
            library="acme",
            from_version="1.0",
            to_version="2.0",
            symbol="Helper",
            kind="deprecated",
            description="Helper deprecated",
            confidence=0.8,
            official_reference="https://example.com/changelog",
        ),
    ]
    usages = [
        {
            "fully_qualified_name": "acme.core.OldAPI",
            "symbol": "OldAPI",
            "module_path": "acme.core",
            "file_path": "src/app.py",
            "line": 10,
            "code_snippet": "OldAPI()",
        },
        {
            "fully_qualified_name": "acme.utils.Helper",
            "symbol": "Helper",
            "module_path": "acme.utils",
            "file_path": "src/util.py",
            "line": 3,
            "code_snippet": "Helper()",
        },
    ]
    matches = matcher.match(rules, usages)
    assert len(matches) == 2
    files = matcher.group_by_file(matches)
    assert {f["file_path"] for f in files} == {"src/app.py", "src/util.py"}


def test_rule_validator_rejects_ungrounded_autofix():
    validator = RuleValidator()
    rule = MigrationRuleDTO(
        library="pkg",
        from_version="1",
        to_version="2",
        symbol="pkg.x",
        kind="renamed",
        description="renamed",
        auto_fixable=True,
        after=None,
        confidence=0.9,
    )
    status, errors = validator.validate_rule(rule)
    assert status == "rejected"
    assert errors


def test_rule_validator_accepts_grounded_rule():
    validator = RuleValidator()
    rule = MigrationRuleDTO(
        library="pkg",
        from_version="1",
        to_version="2",
        symbol="pkg.Old",
        kind="renamed",
        description="Old renamed to New",
        before="from pkg import Old",
        after="from pkg import New",
        auto_fixable=True,
        official_reference="https://example.com/mig",
        confidence=0.85,
    )
    status, errors = validator.validate_rule(rule)
    assert status == "validated"
    assert errors == []


def test_heuristic_generator_extracts_from_release_notes():
    gen = RuleGenerator(ai=_StubAI())  # type: ignore[arg-type]
    batch = gen.generate(
        library="unknownlib",
        from_version="0.1.0",
        to_version="0.2.0",
        documentation_excerpts=[],
        release_notes=[
            {
                "version": "0.2.0",
                "url": "https://github.com/acme/unknownlib/releases/tag/v0.2.0",
                "title": "0.2.0",
                "body": (
                    "Breaking changes\n"
                    "- Removed `unknownlib.legacy.Foo`\n"
                    "- `unknownlib.util.bar` is deprecated\n"
                ),
            }
        ],
    )
    assert batch.rules
    kinds = {r.kind for r in batch.rules}
    assert kinds & {"removed", "deprecated", "behavior_change"}
    assert all(r.official_reference for r in batch.rules)


def test_version_in_range():
    assert version_in_range("1.5.0", "1.0.0", "2.0.0")
    assert not version_in_range("1.0.0", "1.0.0", "2.0.0")
    assert version_in_range("2.0.0", "1.0.0", "2.0.0")


def test_patch_ast_validation():
    from app.migration_engine.models import PatchDTO

    validator = RuleValidator()
    good = validator.validate_patch(
        PatchDTO(
            file_path="a.py",
            current_code="x = 1",
            suggested_code="x = 2",
            reason="bump",
            confidence=0.8,
        )
    )
    assert good.validation_status in {"validated", "needs_review"}

    bad = validator.validate_patch(
        PatchDTO(
            file_path="a.py",
            current_code="x = 1",
            suggested_code="def (",
            reason="bad",
            confidence=0.8,
        )
    )
    assert bad.validation_status == "rejected"
    assert bad.auto_fixable is False
