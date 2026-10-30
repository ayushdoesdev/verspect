"""AST-based Python library usage extractor."""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.core.enums import UsageKind
from app.core.logging import get_logger
from app.scanners.normalize import normalize_package_name

logger = get_logger(__name__)

STDLIB_MODULES = {
    "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio", "asyncore",
    "atexit", "audioop", "base64", "bdb", "binascii", "binhex", "bisect", "builtins",
    "bz2", "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd", "code", "codecs",
    "codeop", "collections", "colorsys", "compileall", "concurrent", "configparser",
    "contextlib", "contextvars", "copy", "copyreg", "cProfile", "crypt", "csv",
    "ctypes", "curses", "dataclasses", "datetime", "dbm", "decimal", "difflib",
    "dis", "distutils", "doctest", "email", "encodings", "enum", "errno",
    "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch", "fractions",
    "ftplib", "functools", "gc", "getopt", "getpass", "gettext", "glob", "graphlib",
    "grp", "gzip", "hashlib", "heapq", "hmac", "html", "http", "idlelib", "imaplib",
    "imghdr", "importlib", "inspect", "io", "ipaddress", "itertools", "json",
    "keyword", "lib2to3", "linecache", "locale", "logging", "lzma", "mailbox",
    "mailcap", "marshal", "math", "mimetypes", "mmap", "modulefinder", "msilib",
    "msvcrt", "multiprocessing", "netrc", "nis", "nntplib", "numbers", "operator",
    "optparse", "os", "ossaudiodev", "pathlib", "pdb", "pickle", "pickletools",
    "pipes", "pkgutil", "platform", "plistlib", "poplib", "posix", "posixpath",
    "pprint", "profile", "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc",
    "queue", "quopri", "random", "re", "readline", "reprlib", "resource", "rlcompleter",
    "runpy", "sched", "secrets", "select", "selectors", "shelve", "shlex", "shutil",
    "signal", "site", "smtpd", "smtplib", "sndhdr", "socket", "socketserver", "spwd",
    "sqlite3", "ssl", "stat", "statistics", "string", "stringprep", "struct",
    "subprocess", "sunau", "symtable", "sys", "sysconfig", "syslog", "tabnanny",
    "tarfile", "telnetlib", "tempfile", "termios", "test", "textwrap", "threading",
    "time", "timeit", "tkinter", "token", "tokenize", "tomllib", "trace", "traceback",
    "tracemalloc", "tty", "turtle", "turtledemo", "types", "typing", "unicodedata",
    "unittest", "urllib", "uu", "uuid", "venv", "warnings", "wave", "weakref",
    "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib", "xml", "xmlrpc",
    "zipapp", "zipfile", "zipimport", "zlib", "zoneinfo", "_thread", "__future__",
}


@dataclass
class UsageRecord:
    package_name: str
    module_path: Optional[str]
    symbol: str
    fully_qualified_name: str
    usage_kind: str
    file_path: str
    line: int
    column: int
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    enclosing_function: Optional[str] = None
    enclosing_class: Optional[str] = None
    code_snippet: Optional[str] = None
    alias: Optional[str] = None
    keyword_args: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ASTScanResult:
    files_parsed: int = 0
    files_failed: int = 0
    usages: list[UsageRecord] = field(default_factory=list)


class _ImportTracker:
    """Maps local names → (package_root, module_path, imported_symbol)."""

    def __init__(self) -> None:
        # alias -> (top_package, full_module, symbol_or_None)
        self.names: dict[str, tuple[str, str, Optional[str]]] = {}

    def add_module(self, module: str, alias: Optional[str] = None) -> None:
        top = module.split(".", 1)[0]
        local = alias or top
        self.names[local] = (top, module, None)
        # Also register full module path for attribute chains starting at package
        if alias is None and "." in module:
            self.names[module.split(".")[0]] = (top, top, None)

    def add_from(self, module: str, name: str, alias: Optional[str] = None) -> None:
        top = module.split(".", 1)[0] if module else name
        local = alias or name
        full_mod = f"{module}.{name}" if module else name
        self.names[local] = (top or name, module or name, name)

    def resolve(self, name: str) -> Optional[tuple[str, str, Optional[str]]]:
        return self.names.get(name)


class LibraryUsageVisitor(ast.NodeVisitor):
    def __init__(
        self,
        file_path: str,
        source_lines: list[str],
        known_packages: set[str],
    ) -> None:
        self.file_path = file_path
        self.source_lines = source_lines
        self.known_packages = known_packages
        self.imports = _ImportTracker()
        self.usages: list[UsageRecord] = []
        self._class_stack: list[str] = []
        self._func_stack: list[str] = []

    def _snippet(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.source_lines):
            return self.source_lines[lineno - 1].rstrip()[:500]
        return ""

    def _is_external(self, package: str) -> bool:
        if package in STDLIB_MODULES:
            return False
        if package.startswith("_") and package.lstrip("_") in STDLIB_MODULES:
            return False
        # Relative / local packages without known mapping are skipped unless known
        if self.known_packages:
            return normalize_package_name(package) in self.known_packages or package in self.known_packages
        return True

    def _record(
        self,
        package: str,
        module_path: Optional[str],
        symbol: str,
        fqn: str,
        kind: str,
        node: ast.AST,
        alias: Optional[str] = None,
        keyword_args: Optional[list[str]] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        if not self._is_external(package):
            return
        lineno = getattr(node, "lineno", 1)
        col = getattr(node, "col_offset", 0)
        self.usages.append(
            UsageRecord(
                package_name=package,
                module_path=module_path,
                symbol=symbol,
                fully_qualified_name=fqn,
                usage_kind=kind,
                file_path=self.file_path,
                line=lineno,
                column=col,
                end_line=getattr(node, "end_lineno", None),
                end_column=getattr(node, "end_col_offset", None),
                enclosing_function=self._func_stack[-1] if self._func_stack else None,
                enclosing_class=self._class_stack[-1] if self._class_stack else None,
                code_snippet=self._snippet(lineno),
                alias=alias,
                keyword_args=list(keyword_args or []),
                context=dict(context or {}),
            )
        )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.add_module(alias.name, alias.asname)
            top = alias.name.split(".", 1)[0]
            self._record(
                top,
                alias.name,
                alias.name,
                alias.name,
                UsageKind.IMPORT.value,
                node,
                alias=alias.asname,
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level and node.level > 0:
            # Relative import — skip (local)
            self.generic_visit(node)
            return
        module = node.module or ""
        top = module.split(".", 1)[0] if module else ""
        for alias in node.names:
            if alias.name == "*":
                self._record(
                    top or "*",
                    module,
                    "*",
                    f"{module}.*" if module else "*",
                    UsageKind.FROM_IMPORT.value,
                    node,
                )
                continue
            self.imports.add_from(module, alias.name, alias.asname)
            fqn = f"{module}.{alias.name}" if module else alias.name
            self._record(
                top or alias.name,
                module,
                alias.name,
                fqn,
                UsageKind.FROM_IMPORT.value,
                node,
                alias=alias.asname,
            )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for base in node.bases:
            self._handle_name_or_attr(base, UsageKind.INHERITANCE.value)
        for dec in node.decorator_list:
            self._handle_name_or_attr(dec, UsageKind.DECORATOR.value)
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function_like(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function_like(node)

    def _visit_function_like(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for dec in node.decorator_list:
            self._handle_name_or_attr(dec, UsageKind.DECORATOR.value)
        if node.returns:
            self._handle_annotation(node.returns)
        for arg in node.args.args + node.args.kwonlyargs:
            if arg.annotation:
                self._handle_annotation(arg.annotation)
        if node.args.vararg and node.args.vararg.annotation:
            self._handle_annotation(node.args.vararg.annotation)
        if node.args.kwarg and node.args.kwarg.annotation:
            self._handle_annotation(node.args.kwarg.annotation)
        self._func_stack.append(node.name)
        self.generic_visit(node)
        self._func_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        kw_names = [kw.arg for kw in node.keywords if kw.arg]
        if isinstance(node.func, ast.Name):
            resolved = self.imports.resolve(node.func.id)
            if resolved:
                pkg, mod, sym = resolved
                if sym:
                    self._record(
                        pkg,
                        mod,
                        sym,
                        f"{mod}.{sym}" if mod else sym,
                        UsageKind.CLASS_INSTANTIATION.value
                        if sym[:1].isupper()
                        else UsageKind.FUNCTION_CALL.value,
                        node,
                        keyword_args=kw_names,
                        context={"call": True, "keyword_args": kw_names},
                    )
                else:
                    self._record(
                        pkg,
                        mod,
                        node.func.id,
                        mod,
                        UsageKind.FUNCTION_CALL.value,
                        node,
                        keyword_args=kw_names,
                        context={"call": True, "keyword_args": kw_names},
                    )
        elif isinstance(node.func, ast.Attribute):
            self._handle_attribute_call(node.func, node, kw_names)
        # Visit arguments only — skip func to avoid duplicate ATTRIBUTE records
        for arg in node.args:
            self.visit(arg)
        for kw in node.keywords:
            if kw.arg is not None and isinstance(kw.value, (ast.Name, ast.Attribute)):
                self._handle_name_or_attr(kw.value, UsageKind.KEYWORD_ARGUMENT.value)
            self.visit(kw.value)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        chain = self._attr_chain(node)
        if len(chain) >= 2:
            resolved = self.imports.resolve(chain[0])
            if resolved:
                pkg, mod, sym = resolved
                parts = ([mod, sym] if sym else [mod]) + chain[1:]
                fqn = ".".join(p for p in parts if p)
                self._record(
                    pkg,
                    mod,
                    chain[-1],
                    fqn,
                    UsageKind.ATTRIBUTE.value,
                    node,
                    context={"attribute_chain": chain},
                )
        # Do not generic_visit Attribute value chain — would re-walk names

    def visit_Assign(self, node: ast.Assign) -> None:
        self._handle_name_or_attr(node.value, UsageKind.ASSIGNMENT.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.annotation:
            self._handle_annotation(node.annotation)
        if node.value is not None:
            self._handle_name_or_attr(node.value, UsageKind.ASSIGNMENT.value)
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            self._handle_name_or_attr(item.context_expr, UsageKind.CONTEXT_MANAGER.value)
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        for item in node.items:
            self._handle_name_or_attr(item.context_expr, UsageKind.CONTEXT_MANAGER.value)
        self.generic_visit(node)

    def _handle_attribute_call(
        self,
        attr: ast.Attribute,
        call: ast.Call,
        kw_names: Optional[list[str]] = None,
    ) -> None:
        chain = self._attr_chain(attr)
        if not chain:
            return
        root = chain[0]
        resolved = self.imports.resolve(root)
        if not resolved:
            return
        pkg, mod, sym = resolved
        kw_names = kw_names or []
        if sym:
            fqn_parts = [mod, sym] + chain[1:] if mod else [sym] + chain[1:]
            fqn = ".".join(p for p in fqn_parts if p)
            kind = UsageKind.METHOD_CALL.value if len(chain) > 1 else (
                UsageKind.CLASS_INSTANTIATION.value
                if sym[:1].isupper()
                else UsageKind.FUNCTION_CALL.value
            )
            self._record(
                pkg,
                mod,
                chain[-1],
                fqn,
                kind,
                call,
                keyword_args=kw_names,
                context={"call": True, "keyword_args": kw_names, "attribute_chain": chain},
            )
        else:
            rest = chain[1:]
            fqn = ".".join([mod] + rest) if rest else mod
            kind = UsageKind.METHOD_CALL.value if rest else UsageKind.FUNCTION_CALL.value
            self._record(
                pkg,
                mod,
                chain[-1],
                fqn,
                kind,
                call,
                keyword_args=kw_names,
                context={"call": True, "keyword_args": kw_names, "attribute_chain": chain},
            )

    def _handle_name_or_attr(self, node: ast.AST, kind: str) -> None:
        if isinstance(node, ast.Call):
            # decorator factory: @decorator()
            self._handle_name_or_attr(node.func, kind)
            return
        if isinstance(node, ast.Name):
            resolved = self.imports.resolve(node.id)
            if resolved:
                pkg, mod, sym = resolved
                fqn = f"{mod}.{sym}" if sym and mod else (sym or mod)
                self._record(pkg, mod, sym or node.id, fqn, kind, node)
        elif isinstance(node, ast.Attribute):
            chain = self._attr_chain(node)
            if not chain:
                return
            resolved = self.imports.resolve(chain[0])
            if resolved:
                pkg, mod, sym = resolved
                parts = ([mod, sym] if sym else [mod]) + chain[1:]
                fqn = ".".join(p for p in parts if p)
                self._record(pkg, mod, chain[-1], fqn, kind, node)

    def _handle_annotation(self, node: ast.AST) -> None:
        if isinstance(node, ast.Constant):
            return
        if isinstance(node, ast.Subscript):
            self._handle_annotation(node.value)
            self._handle_annotation(node.slice)
            return
        if isinstance(node, ast.Tuple):
            for elt in node.elts:
                self._handle_annotation(elt)
            return
        if isinstance(node, ast.BinOp):  # X | Y unions
            self._handle_annotation(node.left)
            self._handle_annotation(node.right)
            return
        self._handle_name_or_attr(node, UsageKind.TYPE_HINT.value)

    @staticmethod
    def _attr_chain(node: ast.AST) -> list[str]:
        parts: list[str] = []
        cur: ast.AST | None = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            parts.reverse()
            return parts
        return []


class ASTParser:
    """Walk a repository and extract third-party library usage."""

    def __init__(
        self,
        repo_path: str | Path,
        known_packages: Optional[set[str]] = None,
        max_file_size_mb: float = 5.0,
    ) -> None:
        self.repo_path = Path(repo_path)
        self.known_packages = {
            normalize_package_name(p) for p in (known_packages or set())
        }
        self.max_bytes = int(max_file_size_mb * 1024 * 1024)

    def scan(self) -> ASTScanResult:
        result = ASTScanResult()
        skip_dirs = {
            ".git", ".venv", "venv", "node_modules", "__pycache__",
            ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
            ".eggs", "site-packages",
        }
        for path in self.repo_path.rglob("*.py"):
            if any(part in skip_dirs for part in path.parts):
                continue
            try:
                if path.stat().st_size > self.max_bytes:
                    continue
                rel = str(path.relative_to(self.repo_path))
                usages = self.parse_file(path, rel)
                result.usages.extend(usages)
                result.files_parsed += 1
            except SyntaxError as exc:
                result.files_failed += 1
                logger.debug("ast_syntax_error", file=str(path), error=str(exc))
            except Exception as exc:
                result.files_failed += 1
                logger.warning("ast_parse_failed", file=str(path), error=str(exc))
        return result

    def parse_file(self, path: Path, rel_path: str) -> list[UsageRecord]:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=rel_path)
        visitor = LibraryUsageVisitor(
            file_path=rel_path,
            source_lines=source.splitlines(),
            known_packages=self.known_packages,
        )
        visitor.visit(tree)
        return visitor.usages
