"""Manifest scanners for Python dependency files."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

import tomli

from app.core.logging import get_logger
from app.scanners.normalize import normalize_package_name, parse_requirement_line, read_text_auto

logger = get_logger(__name__)

MANIFEST_NAMES = {
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
    "dev-requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "uv.lock",
    "Pipfile",
    "Pipfile.lock",
    "setup.cfg",
    "setup.py",
}


@dataclass
class ParsedDependency:
    package_name: str
    normalized_name: str
    version: Optional[str] = None
    constraint: Optional[str] = None
    extras: list[str] = field(default_factory=list)
    marker: Optional[str] = None
    is_dev: bool = False
    is_direct: bool = True
    manifest_source: str = ""
    ecosystem: str = "PyPI"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ManifestScanResult:
    files_found: list[str] = field(default_factory=list)
    dependencies: list[ParsedDependency] = field(default_factory=list)

    def merged_by_name(self) -> list[ParsedDependency]:
        """Prefer locked/exact versions over constraints when merging duplicates."""
        by_name: dict[str, ParsedDependency] = {}
        for dep in self.dependencies:
            key = dep.normalized_name
            existing = by_name.get(key)
            if existing is None:
                by_name[key] = dep
                continue
            # Prefer entry with concrete version
            if dep.version and not existing.version:
                by_name[key] = dep
            elif dep.version and existing.version and not existing.is_direct and dep.is_direct:
                by_name[key] = dep
            # Merge sources
            if dep.manifest_source and dep.manifest_source not in (existing.manifest_source or ""):
                existing.manifest_source = (
                    f"{existing.manifest_source},{dep.manifest_source}"
                    if existing.manifest_source
                    else dep.manifest_source
                )
            if dep.is_dev:
                existing.is_dev = True
        return list(by_name.values())


class ManifestScanner:
    """Discover and parse Python dependency manifests in a repository tree."""

    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = Path(repo_path)

    def scan(self) -> ManifestScanResult:
        result = ManifestScanResult()
        if not self.repo_path.exists():
            logger.warning("repo_path_missing", path=str(self.repo_path))
            return result

        for path in self._discover_manifests():
            rel = str(path.relative_to(self.repo_path))
            result.files_found.append(rel)
            try:
                deps = self._parse_file(path)
                for d in deps:
                    d.manifest_source = rel
                result.dependencies.extend(deps)
                logger.info("manifest_parsed", file=rel, count=len(deps))
            except Exception as exc:
                logger.exception("manifest_parse_failed", file=rel, error=str(exc))

        return result

    def _discover_manifests(self) -> list[Path]:
        found: list[Path] = []
        skip_dirs = {
            ".git",
            ".venv",
            "venv",
            "node_modules",
            "__pycache__",
            ".tox",
            ".mypy_cache",
            ".pytest_cache",
            "dist",
            "build",
            ".eggs",
        }
        for path in self.repo_path.rglob("*"):
            if not path.is_file():
                continue
            if any(part in skip_dirs for part in path.parts):
                continue
            name = path.name
            if name in MANIFEST_NAMES:
                found.append(path)
            elif name.startswith("requirements") and name.endswith(".txt"):
                found.append(path)
        return sorted(found)

    def _parse_file(self, path: Path) -> list[ParsedDependency]:
        name = path.name
        if name.endswith(".txt") and "requirements" in name.lower():
            return self._parse_requirements_txt(path)
        if name == "pyproject.toml":
            return self._parse_pyproject(path)
        if name == "poetry.lock":
            return self._parse_poetry_lock(path)
        if name == "uv.lock":
            return self._parse_uv_lock(path)
        if name == "Pipfile":
            return self._parse_pipfile(path)
        if name == "Pipfile.lock":
            return self._parse_pipfile_lock(path)
        if name == "setup.cfg":
            return self._parse_setup_cfg(path)
        if name == "setup.py":
            return self._parse_setup_py(path)
        return []

    def _parse_requirements_txt(self, path: Path) -> list[ParsedDependency]:
        deps: list[ParsedDependency] = []
        is_dev = any(x in path.name.lower() for x in ("dev", "test", "lint"))
        text = read_text_auto(path)
        for line in text.splitlines():
            # Handle nested -r includes
            stripped = line.strip()
            if stripped.startswith("-r ") or stripped.startswith("--requirement "):
                include = stripped.split(maxsplit=1)[1]
                include_path = (path.parent / include).resolve()
                if include_path.exists() and self.repo_path in include_path.parents or include_path.parent == self.repo_path:
                    deps.extend(self._parse_requirements_txt(include_path))
                continue
            parsed = parse_requirement_line(line)
            if not parsed:
                continue
            deps.append(
                ParsedDependency(
                    package_name=parsed["package_name"],
                    normalized_name=parsed["normalized_name"],
                    version=parsed["version"],
                    constraint=parsed["constraint"],
                    extras=parsed["extras"],
                    marker=parsed["marker"],
                    is_dev=is_dev,
                    is_direct=True,
                )
            )
        return deps

    def _parse_pyproject(self, path: Path) -> list[ParsedDependency]:
        data = tomli.loads(read_text_auto(path))
        deps: list[ParsedDependency] = []

        # PEP 621
        project = data.get("project") or {}
        for req in project.get("dependencies") or []:
            parsed = parse_requirement_line(req)
            if parsed:
                deps.append(self._from_parsed(parsed, is_dev=False))
        optional = project.get("optional-dependencies") or {}
        for group, reqs in optional.items():
            for req in reqs:
                parsed = parse_requirement_line(req)
                if parsed:
                    deps.append(self._from_parsed(parsed, is_dev=group in {"dev", "test", "lint", "docs"}))

        # Poetry
        poetry = (data.get("tool") or {}).get("poetry") or {}
        for name, spec in (poetry.get("dependencies") or {}).items():
            if name.lower() == "python":
                continue
            deps.append(self._from_poetry_spec(name, spec, is_dev=False))
        for group_name, group in (poetry.get("group") or {}).items():
            for name, spec in (group.get("dependencies") or {}).items():
                deps.append(
                    self._from_poetry_spec(
                        name,
                        spec,
                        is_dev=group_name in {"dev", "test", "lint", "docs"},
                    )
                )
        # Legacy poetry.dev-dependencies
        for name, spec in (poetry.get("dev-dependencies") or {}).items():
            deps.append(self._from_poetry_spec(name, spec, is_dev=True))

        return deps

    def _from_poetry_spec(self, name: str, spec: Any, is_dev: bool) -> ParsedDependency:
        version = None
        constraint = None
        extras: list[str] = []
        if isinstance(spec, str):
            constraint = spec if spec != "*" else None
            if constraint and constraint.startswith("^"):
                constraint = f">={constraint[1:]}"
            elif constraint and re.match(r"^[\d]", constraint):
                version = constraint
                constraint = f"=={constraint}"
        elif isinstance(spec, dict):
            ver = spec.get("version")
            if ver and ver != "*":
                constraint = str(ver)
            extras = list(spec.get("extras") or [])
        return ParsedDependency(
            package_name=name,
            normalized_name=normalize_package_name(name),
            version=version,
            constraint=constraint,
            extras=extras,
            is_dev=is_dev,
            is_direct=True,
        )

    def _parse_poetry_lock(self, path: Path) -> list[ParsedDependency]:
        data = tomli.loads(read_text_auto(path))
        deps: list[ParsedDependency] = []
        for pkg in data.get("package") or []:
            name = pkg.get("name")
            if not name:
                continue
            category = pkg.get("category", "main")
            deps.append(
                ParsedDependency(
                    package_name=name,
                    normalized_name=normalize_package_name(name),
                    version=pkg.get("version"),
                    constraint=f"=={pkg['version']}" if pkg.get("version") else None,
                    is_dev=category != "main",
                    is_direct=False,
                )
            )
        return deps

    def _parse_uv_lock(self, path: Path) -> list[ParsedDependency]:
        data = tomli.loads(read_text_auto(path))
        deps: list[ParsedDependency] = []
        for pkg in data.get("package") or []:
            name = pkg.get("name")
            if not name:
                continue
            deps.append(
                ParsedDependency(
                    package_name=name,
                    normalized_name=normalize_package_name(name),
                    version=pkg.get("version"),
                    constraint=f"=={pkg['version']}" if pkg.get("version") else None,
                    is_dev=False,
                    is_direct=False,
                )
            )
        return deps

    def _parse_pipfile(self, path: Path) -> list[ParsedDependency]:
        data = tomli.loads(read_text_auto(path))
        deps: list[ParsedDependency] = []
        for section, is_dev in (("packages", False), ("dev-packages", True)):
            for name, spec in (data.get(section) or {}).items():
                if isinstance(spec, str):
                    constraint = None if spec == "*" else spec
                    version = spec if re.match(r"^==", spec or "") else None
                    if version:
                        version = version.lstrip("=").strip()
                    deps.append(
                        ParsedDependency(
                            package_name=name,
                            normalized_name=normalize_package_name(name),
                            version=version,
                            constraint=constraint,
                            is_dev=is_dev,
                        )
                    )
                elif isinstance(spec, dict):
                    ver = spec.get("version", "*")
                    constraint = None if ver == "*" else str(ver)
                    deps.append(
                        ParsedDependency(
                            package_name=name,
                            normalized_name=normalize_package_name(name),
                            constraint=constraint,
                            is_dev=is_dev,
                        )
                    )
        return deps

    def _parse_pipfile_lock(self, path: Path) -> list[ParsedDependency]:
        data = json.loads(read_text_auto(path))
        deps: list[ParsedDependency] = []
        for section, is_dev in (("default", False), ("develop", True)):
            for name, meta in (data.get(section) or {}).items():
                version = (meta.get("version") or "").lstrip("=")
                deps.append(
                    ParsedDependency(
                        package_name=name,
                        normalized_name=normalize_package_name(name),
                        version=version or None,
                        constraint=f"=={version}" if version else None,
                        is_dev=is_dev,
                        is_direct=False,
                    )
                )
        return deps

    def _parse_setup_cfg(self, path: Path) -> list[ParsedDependency]:
        # Minimal INI-style parse for install_requires
        text = read_text_auto(path)
        deps: list[ParsedDependency] = []
        in_requires = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_requires = stripped in {"[options]", "[options.extras_require]"}
                continue
            if in_requires and stripped.startswith("install_requires"):
                # multiline list may follow
                continue
            if in_requires and stripped and not stripped.startswith("#"):
                # Could be indented requirement under install_requires
                if "=" in stripped and not any(op in stripped for op in (">=", "<=", "==", "~=", "!=")):
                    continue
                parsed = parse_requirement_line(stripped.lstrip())
                if parsed:
                    deps.append(self._from_parsed(parsed, is_dev=False))
        return deps

    def _parse_setup_py(self, path: Path) -> list[ParsedDependency]:
        """Deterministic AST extract of install_requires / extras_require from setup.py."""
        import ast

        text = read_text_auto(path)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            logger.warning("setup_py_parse_failed", file=str(path))
            return []

        deps: list[ParsedDependency] = []

        def _req_list(node: ast.AST) -> list[str]:
            out: list[str] = []
            if isinstance(node, (ast.List, ast.Tuple)):
                for elt in node.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        out.append(elt.value)
            return out

        def _from_call(call: ast.Call) -> None:
            for kw in call.keywords:
                if kw.arg == "install_requires":
                    for req in _req_list(kw.value):
                        parsed = parse_requirement_line(req)
                        if parsed:
                            deps.append(self._from_parsed(parsed, is_dev=False))
                elif kw.arg == "extras_require" and isinstance(kw.value, ast.Dict):
                    for key, val in zip(kw.value.keys, kw.value.values):
                        is_dev = False
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            is_dev = key.value.lower() in {"dev", "test", "lint", "docs"}
                        for req in _req_list(val):
                            parsed = parse_requirement_line(req)
                            if parsed:
                                deps.append(self._from_parsed(parsed, is_dev=is_dev))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = None
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name == "setup":
                    _from_call(node)

        return deps

    @staticmethod
    def _from_parsed(parsed: dict, is_dev: bool) -> ParsedDependency:
        return ParsedDependency(
            package_name=parsed["package_name"],
            normalized_name=parsed["normalized_name"],
            version=parsed["version"],
            constraint=parsed["constraint"],
            extras=parsed["extras"],
            marker=parsed["marker"],
            is_dev=is_dev or parsed.get("is_dev", False),
            is_direct=True,
        )
