"""NumPy 1.x → 2.0 removed alias migration (deterministic catalog)."""

from __future__ import annotations

from app.migration_engine.patch_generator import PatchGenerator
from app.migration_engine.rule_catalog import rules_for_upgrade
from app.migration_engine.rule_matcher import RuleMatcher
from app.migration_engine.semantic_index import SemanticASTIndex
from app.scanners.ast_parser import ASTParser

SAMPLE = """\
import numpy as np

arr = np.array([1, 2, 3], dtype=np.float)
i = np.int(3)
flag = np.bool(True)
obj = np.object()
c = np.complex(1, 2)
"""

ALIASES = {
    "float": "float",
    "int": "int",
    "bool": "bool",
    "object": "object",
    "complex": "complex",
}


def test_numpy_catalog_crosses_2_0():
    rules = rules_for_upgrade("numpy", "1.26.4", "2.0.2")
    by_sym = {r.symbol: r for r in rules}
    for sym, repl in ALIASES.items():
        assert sym in by_sym
        assert by_sym[sym].after == repl
        assert by_sym[sym].auto_fixable is True
        assert by_sym[sym].kind == "removed"

    assert rules_for_upgrade("numpy", "2.0.0", "2.1.0") == []
    assert rules_for_upgrade("numpy", "1.24.0", "1.26.4") == []


def test_numpy_v2_removed_aliases_detected(tmp_path):
    src = tmp_path / "main.py"
    src.write_text(SAMPLE, encoding="utf-8")

    result = ASTParser(tmp_path, known_packages={"numpy"}).scan()
    usages = [u.to_dict() for u in result.usages]

    fqns = {u["fully_qualified_name"] for u in usages}
    symbols = {u["symbol"] for u in usages}
    print("Detected symbols:", sorted(symbols))
    print("Detected API usages:", sorted(fqns))

    assert "numpy.float" in fqns
    assert "float" in symbols
    for sym in ALIASES:
        assert f"numpy.{sym}" in fqns

    rules = rules_for_upgrade("numpy", "1.26.4", "2.0.0")
    index = SemanticASTIndex.from_usage_dicts(usages).filter_package("numpy")
    matches = RuleMatcher().match_index(index, rules)
    matched_syms = {m.symbol for m in matches}
    print("Matched rules:", sorted({(m.rule.symbol, m.rule.after) for m in matches}))
    print("Matched usage symbols:", sorted(matched_syms))

    for sym in ALIASES:
        assert any(m.rule.symbol == sym for m in matches), f"missing match for {sym}"

    patches, findings = PatchGenerator().generate(matches)
    print(
        "Generated patches:",
        [(p.symbol, p.suggested_code) for p in patches],
    )

    auto = [f for f in findings if f.status == "automatic_migration"]
    by_leaf = {(f.symbol or "").split(".")[-1]: f for f in auto}

    for sym, repl in ALIASES.items():
        finding = by_leaf.get(sym)
        assert finding is not None, f"no automatic finding for {sym}"
        assert finding.replacement == repl
        assert finding.confidence >= 0.95
        assert finding.suggested_code is not None
        assert f"np.{sym}" not in (finding.suggested_code or "")
        assert repl in (finding.suggested_code or "")

    assert len(patches) >= 5
    assert any("dtype=float" in (p.suggested_code or "") for p in patches)


def test_numpy_float_alone_not_no_changes(tmp_path):
    """Regression: dtype=np.float must not report No Changes Required."""
    (tmp_path / "arr.py").write_text(
        "import numpy as np\narr = np.array([1, 2, 3], dtype=np.float)\n",
        encoding="utf-8",
    )
    usages = [
        u.to_dict()
        for u in ASTParser(tmp_path, known_packages={"numpy"}).scan().usages
    ]
    rules = rules_for_upgrade("numpy", "1.26.4", "2.1.0")
    matches = RuleMatcher().match(
        rules, SemanticASTIndex.from_usage_dicts(usages).filter_package("numpy")
    )
    _, findings = PatchGenerator().generate(matches)
    float_findings = [
        f for f in findings if (f.symbol or "").endswith("float") or f.symbol == "float"
    ]
    assert float_findings
    assert all(f.status == "automatic_migration" for f in float_findings)
    assert all(f.status != "no_migration_required" for f in float_findings)
