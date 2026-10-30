"""Deterministic Rule Matcher — Semantic AST × structured Migration Rules.

Never uses AI.
Never invents replacements — replacement comes only from rule.after.
Requires match_kind alignment when specified (e.g. decorator ↔ decorator).
"""

from __future__ import annotations

from typing import Any

from app.migration_engine.models import MatchedUsage, MigrationRuleDTO
from app.migration_engine.semantic_index import SemanticASTIndex, SemanticNode

# Compatible kind aliases for matching
_KIND_ALIASES: dict[str, set[str]] = {
    "decorator": {"decorator"},
    "import": {"import", "from_import"},
    "from_import": {"import", "from_import"},
    "function_call": {"function_call", "class_instantiation"},
    "class_instantiation": {"function_call", "class_instantiation"},
    "method_call": {"method_call"},
    # keyword_argument: dtype=np.float etc. (AST also emits attribute; either is fine)
    "attribute": {"attribute", "method_call", "keyword_argument"},
    "inheritance": {"inheritance"},
    "type_hint": {"type_hint"},
    "assignment": {"assignment"},
    "keyword_argument": {"keyword_argument"},
    "context_manager": {"context_manager"},
}


class RuleMatcher:
    """Pure deterministic matcher."""

    MIN_CONFIDENCE = 0.6

    def match(
        self,
        rules: list[MigrationRuleDTO],
        usages: list[dict[str, Any]] | SemanticASTIndex,
    ) -> list[MatchedUsage]:
        if isinstance(usages, SemanticASTIndex):
            index = usages
        else:
            index = SemanticASTIndex.from_usage_dicts(usages)
        return self.match_index(index, rules)

    def match_index(
        self,
        index: SemanticASTIndex,
        rules: list[MigrationRuleDTO],
    ) -> list[MatchedUsage]:
        # Never match security-kind rules in migration pipeline
        mig_rules = [r for r in rules if r.kind not in {"security"}]
        if not mig_rules:
            return []

        matches: list[MatchedUsage] = []
        seen: set[tuple[str, str, str, int | None, str]] = set()

        for node in index.nodes:
            for rule in mig_rules:
                score = self._score(rule, node)
                if score < self.MIN_CONFIDENCE:
                    continue
                key = (rule.symbol, rule.kind, node.file_path, node.line, node.kind)
                if key in seen:
                    continue
                seen.add(key)
                matches.append(
                    MatchedUsage(
                        rule=rule,
                        file_path=node.file_path,
                        line=node.line,
                        column=node.column,
                        symbol=node.symbol or rule.symbol,
                        fully_qualified_name=node.fully_qualified_name or rule.symbol,
                        usage_kind=node.kind,
                        enclosing_function=node.enclosing_function,
                        enclosing_class=node.enclosing_class,
                        code_snippet=node.code_snippet,
                        match_confidence=round(min(1.0, score * float(rule.confidence or 1.0)), 3),
                    )
                )
        return matches

    def match_detailed(
        self,
        index: SemanticASTIndex,
        rules: list[MigrationRuleDTO],
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in self.match_index(index, rules):
            out.append(
                {
                    "affected_symbol": m.fully_qualified_name,
                    "affected_file": m.file_path,
                    "affected_line": m.line,
                    "usage_kind": m.usage_kind,
                    "replacement": None if m.rule.unchanged else m.rule.after,
                    "confidence": m.match_confidence,
                    "rule_id": m.rule.id,
                    "rule_symbol": m.rule.symbol,
                    "rule_kind": m.rule.kind,
                    "unchanged": m.rule.unchanged,
                    "severity": m.rule.severity,
                    "description": m.rule.description,
                    "official_reference": m.rule.official_reference or m.rule.source_url,
                    "reference_title": m.rule.reference_title,
                    "auto_fixable": bool(
                        m.rule.auto_fixable and m.rule.after and not m.rule.unchanged
                    ),
                    "before": m.rule.before,
                    "code_snippet": m.code_snippet,
                }
            )
        return out

    def _kind_compatible(self, rule: MigrationRuleDTO, node: SemanticNode) -> bool:
        mk = (rule.match_kind or "").strip().lower()
        if not mk:
            return True
        allowed = _KIND_ALIASES.get(mk, {mk})
        return node.kind.lower() in allowed

    def _score(self, rule: MigrationRuleDTO, node: SemanticNode) -> float:
        if not self._kind_compatible(rule, node):
            return 0.0

        rs = (rule.symbol or "").strip()
        if not rs:
            return 0.0
        rs_l = rs.lower()
        fqn_l = (node.fully_qualified_name or "").lower()
        sym_l = (node.symbol or "").lower()
        leaf_rule = rs_l.split(".")[-1].lstrip(".")

        # Method-call rules like ".dict" match attribute/method leaf
        if rs_l.startswith("."):
            leaf = rs_l.lstrip(".")
            if sym_l == leaf or fqn_l.endswith("." + leaf) or fqn_l.endswith(leaf):
                return 1.0
            if leaf in (node.code_snippet or "").lower():
                return 0.85
            return 0.0

        # Exact / leaf symbol match (structured)
        if sym_l == rs_l or sym_l == leaf_rule:
            return 1.0
        if fqn_l == rs_l or fqn_l.endswith("." + leaf_rule):
            return 0.98
        if leaf_rule and leaf_rule == fqn_l.split(".")[-1]:
            return 0.95

        return 0.0

    def group_by_file(self, matches: list[MatchedUsage]) -> list[dict[str, Any]]:
        files: dict[str, dict[str, Any]] = {}
        for m in matches:
            item = files.get(m.file_path)
            if item is None:
                item = {
                    "file_path": m.file_path,
                    "affected_apis": [],
                    "rules": [],
                    "enclosing_functions": [],
                    "enclosing_classes": [],
                    "reason": "",
                    "confidence": 0.0,
                }
                files[m.file_path] = item
            if m.fully_qualified_name not in item["affected_apis"]:
                item["affected_apis"].append(m.fully_qualified_name)
            item["rules"].append(
                {
                    "symbol": m.rule.symbol,
                    "kind": m.rule.kind,
                    "severity": m.rule.severity,
                    "description": m.rule.description,
                    "official_reference": m.rule.official_reference,
                    "replacement": m.rule.after,
                    "unchanged": m.rule.unchanged,
                }
            )
            if m.enclosing_function and m.enclosing_function not in item["enclosing_functions"]:
                item["enclosing_functions"].append(m.enclosing_function)
            if m.enclosing_class and m.enclosing_class not in item["enclosing_classes"]:
                item["enclosing_classes"].append(m.enclosing_class)
            item["confidence"] = max(item["confidence"], m.match_confidence)
            item["reason"] = (
                f"{len(item['affected_apis'])} API(s) match migration rules "
                f"(kinds: {', '.join(sorted({r['kind'] for r in item['rules']}))})."
            )
        return list(files.values())
