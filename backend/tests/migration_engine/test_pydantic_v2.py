"""Pydantic v1 → v2 migration engine acceptance test (deterministic)."""

from __future__ import annotations

from app.migration_engine.models import MigrationRuleDTO
from app.migration_engine.patch_generator import PatchGenerator
from app.migration_engine.rule_catalog import rules_for_upgrade
from app.migration_engine.rule_matcher import RuleMatcher
from app.migration_engine.semantic_index import SemanticASTIndex
from app.scanners.ast_parser import ASTParser


SAMPLE = '''\
from pydantic import BaseModel, validator

class User(BaseModel):

    @validator("name")
    def validate_name(cls, value):
        return value
'''


def test_pydantic_v1_to_v2_basemodel_and_validator(tmp_path):
    src = tmp_path / "user.py"
    src.write_text(SAMPLE, encoding="utf-8")

    parser = ASTParser(tmp_path, known_packages={"pydantic"})
    result = parser.scan()
    usages = [u.to_dict() for u in result.usages]

    kinds = {u["usage_kind"] for u in usages}
    symbols = {u["symbol"] for u in usages}
    assert "decorator" in kinds
    assert "validator" in symbols
    assert "BaseModel" in symbols

    rules = rules_for_upgrade("pydantic", "1.10.0", "2.5.0")
    assert rules
    assert any(r.symbol == "validator" and r.after == "@field_validator" for r in rules)
    assert any(r.symbol == "BaseModel" and r.unchanged for r in rules)

    index = SemanticASTIndex.from_usage_dicts(usages).filter_package("pydantic")
    matches = RuleMatcher().match_index(index, rules)
    assert matches

    patches, findings = PatchGenerator().generate(matches)

    by_symbol: dict[str, object] = {}
    for f in findings:
        leaf = (f.symbol or "").split(".")[-1]
        # Prefer auto over no-change when both exist for same leaf on different kinds
        prev = by_symbol.get(leaf)
        if prev is None:
            by_symbol[leaf] = f
        elif f.status == "automatic_migration":
            by_symbol[leaf] = f

    base = by_symbol.get("BaseModel")
    assert base is not None
    assert base.status == "no_migration_required"

    val = by_symbol.get("validator")
    assert val is not None
    assert val.status == "automatic_migration"
    assert val.replacement == "@field_validator"
    assert val.confidence >= 0.99
    assert "Deprecated" in (val.reason or "")
    assert val.suggested_code is not None
    assert "@field_validator" in val.suggested_code
    assert "@validator" in (val.current_code or "")
    assert val.unified_diff
    assert "- @validator" in val.unified_diff or '-@validator' in val.unified_diff.replace(" ", "")
    assert "+ @field_validator" in val.unified_diff or "+@field_validator" in val.unified_diff.replace(
        " ", ""
    )

    assert patches
    assert any("@field_validator" in p.suggested_code for p in patches)


def test_security_url_never_migration_source():
    from app.migration_engine.documentation_fetcher import DocumentationFetcher, is_security_url

    assert is_security_url("https://github.com/pydantic/pydantic/security/advisories")
    assert is_security_url("https://github.com/advisories/GHSA-xxxx")
    fetcher = DocumentationFetcher()
    urls = fetcher.discover_urls(
        {
            "info": {
                "project_urls": {
                    "Documentation": "https://docs.pydantic.dev/",
                    "Security": "https://github.com/pydantic/pydantic/security",
                    "Changelog": "https://docs.pydantic.dev/changelog/",
                    "Migration": "https://docs.pydantic.dev/latest/migration/",
                }
            }
        }
    )
    assert all("security" not in u["url"].lower() for u in urls)
    types = {u["source_type"] for u in urls}
    assert "migration_guide" in types or any("migrat" in u["url"].lower() for u in urls)


def test_matcher_requires_decorator_kind_for_validator_rule():
    rules = [
        MigrationRuleDTO(
            library="pydantic",
            from_version="1",
            to_version="2",
            symbol="validator",
            match_kind="decorator",
            kind="renamed",
            description="x",
            before="@validator",
            after="@field_validator",
            confidence=0.99,
            auto_fixable=True,
        )
    ]
    # Import of validator should NOT match decorator rule
    index = SemanticASTIndex.from_usage_dicts(
        [
            {
                "package_name": "pydantic",
                "symbol": "validator",
                "fully_qualified_name": "pydantic.validator",
                "usage_kind": "from_import",
                "file_path": "a.py",
                "line": 1,
                "code_snippet": "from pydantic import validator",
            }
        ]
    )
    assert RuleMatcher().match_index(index, rules) == []

    index2 = SemanticASTIndex.from_usage_dicts(
        [
            {
                "package_name": "pydantic",
                "symbol": "validator",
                "fully_qualified_name": "pydantic.validator",
                "usage_kind": "decorator",
                "file_path": "a.py",
                "line": 5,
                "code_snippet": '@validator("name")',
            }
        ]
    )
    matches = RuleMatcher().match_index(index2, rules)
    assert len(matches) == 1
