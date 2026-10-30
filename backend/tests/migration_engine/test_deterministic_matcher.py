"""Tests for deterministic Semantic AST Index + Rule Matcher (no AI)."""

from app.migration_engine.models import MigrationRuleDTO
from app.migration_engine.rule_matcher import RuleMatcher
from app.migration_engine.semantic_index import SemanticASTIndex
from app.scanners.ast_parser import ASTParser


def test_semantic_index_from_usages():
    index = SemanticASTIndex.from_usage_dicts(
        [
            {
                "package_name": "pkg",
                "symbol": "Foo",
                "fully_qualified_name": "pkg.Foo",
                "usage_kind": "import",
                "file_path": "a.py",
                "line": 1,
                "keyword_args": [],
            },
            {
                "package_name": "pkg",
                "symbol": "bar",
                "fully_qualified_name": "pkg.util.bar",
                "usage_kind": "function_call",
                "file_path": "b.py",
                "line": 10,
                "code_snippet": "bar()",
            },
        ]
    )
    assert len(index) == 2
    assert index.files() == ["a.py", "b.py"]
    assert "pkg.Foo" in index.symbols()


def test_rule_matcher_deterministic_no_invention():
    index = SemanticASTIndex.from_usage_dicts(
        [
            {
                "package_name": "acme",
                "symbol": "OldAPI",
                "fully_qualified_name": "acme.core.OldAPI",
                "usage_kind": "function_call",
                "file_path": "src/app.py",
                "line": 4,
                "code_snippet": "OldAPI()",
            }
        ]
    )
    rules = [
        MigrationRuleDTO(
            library="acme",
            from_version="1.0",
            to_version="2.0",
            symbol="acme.core.OldAPI",
            kind="renamed",
            description="OldAPI renamed to NewAPI",
            before="OldAPI",
            after="NewAPI",
            auto_fixable=True,
            confidence=0.9,
            official_reference="https://example.com",
        )
    ]
    matcher = RuleMatcher()
    matches = matcher.match_index(index, rules)
    assert len(matches) == 1
    assert matches[0].rule.after == "NewAPI"
    detailed = matcher.match_detailed(index, rules)
    assert detailed[0]["replacement"] == "NewAPI"
    assert detailed[0]["affected_line"] == 4


def test_rule_matcher_no_rules_means_no_matches():
    index = SemanticASTIndex.from_usage_dicts(
        [
            {
                "package_name": "x",
                "symbol": "y",
                "fully_qualified_name": "x.y",
                "usage_kind": "import",
                "file_path": "a.py",
                "line": 1,
            }
        ]
    )
    assert RuleMatcher().match_index(index, []) == []


def test_ast_parser_indexes_calls_and_kwargs(tmp_path):
    src = tmp_path / "m.py"
    src.write_text(
        "from acme.core import OldAPI\n"
        "import acme\n"
        "\n"
        "class T(acme.Base):\n"
        "    @acme.decorator\n"
        "    def run(self) -> acme.Result:\n"
        "        x = OldAPI(timeout=1)\n"
        "        return acme.util.helper(x)\n",
        encoding="utf-8",
    )
    parser = ASTParser(tmp_path, known_packages={"acme"})
    result = parser.scan()
    kinds = {u.usage_kind for u in result.usages}
    assert "from_import" in kinds or "import" in kinds
    assert "function_call" in kinds or "class_instantiation" in kinds
    assert "inheritance" in kinds
    assert "decorator" in kinds
    assert "type_hint" in kinds
    # keyword_args captured on call
    calls = [u for u in result.usages if u.keyword_args]
    assert any("timeout" in u.keyword_args for u in calls)


def test_engine_patches_only_from_rules():
    from app.migration_engine.models import MatchedUsage
    from app.migration_engine.patch_generator import PatchGenerator

    m = MatchedUsage(
        rule=MigrationRuleDTO(
            library="acme",
            from_version="1",
            to_version="2",
            symbol="acme.Old",
            kind="removed",
            description="removed",
            after=None,
            confidence=0.8,
        ),
        file_path="a.py",
        line=1,
        symbol="Old",
        fully_qualified_name="acme.Old",
        code_snippet="Old()",
        match_confidence=0.9,
    )
    patches, findings = PatchGenerator().generate([m])
    # No grounded replacement → no fake patch
    assert patches == []
    assert findings[0].status == "manual_review_required"
