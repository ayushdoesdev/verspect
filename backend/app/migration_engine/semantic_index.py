"""Semantic AST Index — deterministic source of truth for migration matching.

Indexes imports, decorators, calls, attributes, kwargs, inheritance,
type annotations, assignments, and enclosing context with file/line locations.

No AI involved.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Optional

from app.scanners.normalize import normalize_package_name


@dataclass
class SemanticNode:
    """One semantic usage site in the repository."""

    kind: str
    package_name: str
    symbol: str
    fully_qualified_name: str
    file_path: str
    line: int
    column: int = 0
    module_path: Optional[str] = None
    end_line: Optional[int] = None
    enclosing_function: Optional[str] = None
    enclosing_class: Optional[str] = None
    code_snippet: Optional[str] = None
    alias: Optional[str] = None
    keyword_args: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SemanticASTIndex:
    """
    Deterministic index of library usage sites.

    Built from AST UsageRecords / LibraryUsage dicts.
    This is the source of truth for every migration match.
    """

    SEMANTIC_KINDS = frozenset(
        {
            "import",
            "from_import",
            "function_call",
            "method_call",
            "class_instantiation",
            "decorator",
            "inheritance",
            "context_manager",
            "type_hint",
            "attribute",
            "keyword_argument",
            "assignment",
        }
    )

    def __init__(self, nodes: Optional[list[SemanticNode]] = None) -> None:
        self.nodes: list[SemanticNode] = list(nodes or [])

    @classmethod
    def from_usage_dicts(cls, usages: Iterable[dict[str, Any]]) -> "SemanticASTIndex":
        nodes: list[SemanticNode] = []
        for u in usages:
            meta = u.get("extra_metadata") or u.get("context") or {}
            if not isinstance(meta, dict):
                meta = {}
            kw = u.get("keyword_args") or meta.get("keyword_args") or []
            if isinstance(kw, str):
                kw = [kw]
            kind = (u.get("usage_kind") or "import").strip()
            nodes.append(
                SemanticNode(
                    kind=kind,
                    package_name=u.get("package_name") or "",
                    symbol=(u.get("symbol") or "").strip(),
                    fully_qualified_name=(u.get("fully_qualified_name") or "").strip(),
                    file_path=u.get("file_path") or "",
                    line=int(u.get("line") or 0),
                    column=int(u.get("column") or 0),
                    module_path=u.get("module_path"),
                    end_line=u.get("end_line"),
                    enclosing_function=u.get("enclosing_function"),
                    enclosing_class=u.get("enclosing_class"),
                    code_snippet=u.get("code_snippet"),
                    alias=u.get("alias"),
                    keyword_args=list(kw),
                    context=dict(meta),
                )
            )
        return cls(nodes)

    @classmethod
    def from_usage_records(cls, records: Iterable[Any]) -> "SemanticASTIndex":
        dicts = []
        for r in records:
            if hasattr(r, "to_dict"):
                dicts.append(r.to_dict())
            elif isinstance(r, dict):
                dicts.append(r)
        return cls.from_usage_dicts(dicts)

    def filter_package(self, package_name: str) -> "SemanticASTIndex":
        norm = normalize_package_name(package_name)
        filtered = [
            n
            for n in self.nodes
            if normalize_package_name(n.package_name) == norm
            or n.fully_qualified_name.lower().startswith(norm.replace("-", "_"))
            or n.fully_qualified_name.lower().startswith(package_name.lower())
        ]
        # If package filter empties (usages stored under import name), keep all
        return SemanticASTIndex(filtered if filtered else list(self.nodes))

    def by_kind(self, *kinds: str) -> list[SemanticNode]:
        wanted = {k.lower() for k in kinds}
        return [n for n in self.nodes if n.kind.lower() in wanted]

    def files(self) -> list[str]:
        return sorted({n.file_path for n in self.nodes if n.file_path})

    def symbols(self) -> list[str]:
        return sorted({n.fully_qualified_name for n in self.nodes if n.fully_qualified_name})

    def __len__(self) -> int:
        return len(self.nodes)

    def to_usage_dicts(self) -> list[dict[str, Any]]:
        """Compatibility shape for existing helpers (affected files, etc.)."""
        out = []
        for n in self.nodes:
            out.append(
                {
                    "package_name": n.package_name,
                    "module_path": n.module_path,
                    "symbol": n.symbol,
                    "fully_qualified_name": n.fully_qualified_name,
                    "usage_kind": n.kind,
                    "file_path": n.file_path,
                    "line": n.line,
                    "column": n.column,
                    "end_line": n.end_line,
                    "enclosing_function": n.enclosing_function,
                    "enclosing_class": n.enclosing_class,
                    "code_snippet": n.code_snippet,
                    "alias": n.alias,
                    "keyword_args": n.keyword_args,
                    "extra_metadata": n.context,
                }
            )
        return out
