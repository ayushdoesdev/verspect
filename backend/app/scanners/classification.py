"""Repository classification — language, package manager, framework detection.

This stage runs after clone and before any language-specific analysis.
It does NOT implement scanning for non-Python ecosystems; it only detects
signals so the pipeline can route correctly.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.core.enums import LanguageSupportStatus
from app.core.logging import get_logger
from app.scanners.language_support import (
    display_name_for_language,
    support_label_for,
    support_status_for_language,
)

logger = get_logger(__name__)

# Skip noisy / vendored trees when walking evidence.
_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    "vendor",
    "target",
    ".next",
    "coverage",
}


@dataclass
class ClassificationResult:
    """Structured repository classification used by pipelines and the UI."""

    language: str  # Display name, e.g. "Python"
    language_id: str  # Stable id, e.g. "python"
    support_status: str  # LanguageSupportStatus value
    support_label: str  # "Fully Supported" | "Coming Soon" | "Unknown"
    package_manager: Optional[str] = None
    package_managers: list[str] = field(default_factory=list)
    framework: Optional[str] = None
    frameworks: list[str] = field(default_factory=list)
    confidence: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)
    message: str = ""

    @property
    def is_fully_supported(self) -> bool:
        return self.support_status == LanguageSupportStatus.FULLY_SUPPORTED.value

    @property
    def is_supported(self) -> bool:
        return self.support_status in {
            LanguageSupportStatus.FULLY_SUPPORTED.value,
            LanguageSupportStatus.SUPPORTED.value,
        }

    @property
    def can_analyze(self) -> bool:
        return self.is_supported

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RepositoryClassifier:
    """Detect primary language / package manager / framework from repo files."""

    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = Path(repo_path)

    def classify(self) -> ClassificationResult:
        if not self.repo_path.exists():
            return self._unknown("Repository path missing after clone.")

        scores: dict[str, float] = {}
        evidence: dict[str, Any] = {
            "manifests": [],
            "markers": [],
            "source_counts": {},
        }
        package_managers: list[str] = []
        frameworks: list[str] = []

        def add_lang(lang: str, weight: float, marker: str) -> None:
            scores[lang] = scores.get(lang, 0.0) + weight
            evidence["markers"].append({"language": lang, "signal": marker, "weight": weight})

        def add_pm(name: str) -> None:
            if name not in package_managers:
                package_managers.append(name)

        def add_fw(name: str) -> None:
            if name not in frameworks:
                frameworks.append(name)

        # --- Manifest / lockfile signals (high confidence) ---
        python_manifests = [
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
            "constraints.txt",
        ]
        for rel in self._find_files(python_manifests):
            evidence["manifests"].append(rel)
            add_lang("python", 5.0, rel)
            name = Path(rel).name.lower()
            if name.startswith("requirements") or name == "constraints.txt":
                add_pm("pip")
            elif name in {"poetry.lock", "pyproject.toml"}:
                # Distinguish poetry vs pep621 later from content
                add_pm("poetry" if name == "poetry.lock" else "pip")
            elif name in {"Pipfile", "Pipfile.lock"}:
                add_pm("pipenv")
            elif name == "uv.lock":
                add_pm("uv")
            elif name in {"setup.py", "setup.cfg"}:
                add_pm("setuptools")

        # Refine pyproject package manager / frameworks
        for rel in [m for m in evidence["manifests"] if m.endswith("pyproject.toml")]:
            self._inspect_pyproject(self.repo_path / rel, add_pm, add_fw, add_lang)

        for rel in [m for m in evidence["manifests"] if Path(m).name.startswith("requirements")]:
            self._inspect_requirements(self.repo_path / rel, add_fw)

        if (self.repo_path / "manage.py").exists():
            add_lang("python", 3.0, "manage.py")
            add_fw("Django")

        # Node / JS / TS
        for rel in self._find_files(
            [
                "package.json",
                "package-lock.json",
                "yarn.lock",
                "pnpm-lock.yaml",
                "bun.lockb",
            ]
        ):
            evidence["manifests"].append(rel)
            name = Path(rel).name
            if name == "package.json":
                add_lang("javascript", 5.0, rel)
                self._inspect_package_json(self.repo_path / rel, add_fw, add_lang)
            elif name == "package-lock.json":
                add_lang("javascript", 2.0, rel)
                add_pm("npm")
            elif name == "yarn.lock":
                add_lang("javascript", 2.0, rel)
                add_pm("yarn")
            elif name == "pnpm-lock.yaml":
                add_lang("javascript", 2.0, rel)
                add_pm("pnpm")
            elif name == "bun.lockb":
                add_lang("javascript", 2.0, rel)
                add_pm("bun")
        if any(m.endswith("package.json") for m in evidence["manifests"]) and "npm" not in package_managers:
            # Default package manager when only package.json exists
            if not any(pm in package_managers for pm in ("yarn", "pnpm", "bun")):
                add_pm("npm")

        # Go
        for rel in self._find_files(["go.mod", "go.sum"]):
            evidence["manifests"].append(rel)
            add_lang("go", 5.0 if rel.endswith("go.mod") else 2.0, rel)
            add_pm("go modules")

        # Java / Kotlin
        for rel in self._find_files(["pom.xml", "build.gradle", "build.gradle.kts"]):
            evidence["manifests"].append(rel)
            add_lang("java", 5.0, rel)
            if rel.endswith("pom.xml"):
                add_pm("maven")
            else:
                add_pm("gradle")
                if rel.endswith(".kts"):
                    add_lang("kotlin", 2.0, rel)

        # PHP
        for rel in self._find_files(["composer.json", "composer.lock"]):
            evidence["manifests"].append(rel)
            add_lang("php", 5.0 if rel.endswith("composer.json") else 2.0, rel)
            add_pm("composer")

        # Rust
        for rel in self._find_files(["Cargo.toml", "Cargo.lock"]):
            evidence["manifests"].append(rel)
            add_lang("rust", 5.0 if rel.endswith("Cargo.toml") else 2.0, rel)
            add_pm("cargo")

        # Ruby
        for rel in self._find_files(["Gemfile", "Gemfile.lock"]):
            evidence["manifests"].append(rel)
            add_lang("ruby", 5.0 if Path(rel).name == "Gemfile" else 2.0, rel)
            add_pm("bundler")

        # C#
        for rel in self._find_files_by_suffix([".csproj", ".sln"]):
            evidence["manifests"].append(rel)
            add_lang("csharp", 4.0, rel)
            add_pm("nuget")

        # Source extension counts (lower weight)
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".java": "java",
            ".kt": "kotlin",
            ".php": "php",
            ".rs": "rust",
            ".rb": "ruby",
            ".cs": "csharp",
        }
        counts = self._count_source_files(ext_map)
        evidence["source_counts"] = counts
        for lang, count in counts.items():
            if count <= 0:
                continue
            # Cap contribution so a few files don't override manifests
            add_lang(lang, min(3.0, count / 20.0), f"{count} source files")

        # TypeScript vs JavaScript preference
        if scores.get("typescript", 0) > 0 and scores.get("javascript", 0) > 0:
            if counts.get("typescript", 0) >= counts.get("javascript", 0):
                scores["typescript"] = scores.get("typescript", 0) + scores.get("javascript", 0) * 0.25
            else:
                scores["javascript"] = scores.get("javascript", 0) + scores.get("typescript", 0) * 0.25

        if not scores:
            return self._unknown("No recognizable language or package manager signals found.")

        language_id = max(scores.items(), key=lambda kv: kv[1])[0]
        # Prefer javascript display when both JS ecosystem signals exist without strong TS
        if language_id == "typescript" and scores.get("javascript", 0) >= scores.get("typescript", 0):
            language_id = "javascript"

        support = support_status_for_language(language_id)
        display = display_name_for_language(language_id)

        total = sum(scores.values()) or 1.0
        confidence = round(min(1.0, scores[language_id] / total + 0.15), 2)

        support_label = support_label_for(support)

        if support == LanguageSupportStatus.FULLY_SUPPORTED:
            message = (
                f"{display} is fully supported. Verspect will analyze dependencies, "
                "security, upgrades, and migrations for this repository."
            )
        elif support == LanguageSupportStatus.SUPPORTED:
            message = (
                f"{display} is supported. Verspect analyzes dependencies, usage, "
                "security, licenses, and health. Deterministic upgrade-impact "
                "catalog coverage is currently Python-specific."
            )
        elif support == LanguageSupportStatus.COMING_SOON:
            message = (
                f"{display} repositories are not yet supported. "
                "Verspect currently analyzes Python, JavaScript/TypeScript, Go, Java, "
                "Rust, PHP, and Ruby. "
                "This repository was classified successfully and will be eligible "
                "when language support ships."
            )
        else:
            message = "Could not confidently classify this repository."

        # Prefer package managers relevant to the winning language
        pm = self._primary_package_manager(language_id, package_managers)
        fw = frameworks[0] if frameworks else None

        result = ClassificationResult(
            language=display,
            language_id=language_id if language_id != "javascript" else "javascript",
            support_status=support.value,
            support_label=support_label,
            package_manager=pm,
            package_managers=package_managers,
            framework=fw,
            frameworks=frameworks,
            confidence=confidence,
            evidence=evidence,
            message=message,
        )
        logger.info(
            "repository_classified",
            language=result.language,
            language_id=result.language_id,
            support_status=result.support_status,
            package_manager=result.package_manager,
            framework=result.framework,
            confidence=result.confidence,
        )
        return result

    def _unknown(self, message: str) -> ClassificationResult:
        return ClassificationResult(
            language="Unknown",
            language_id="unknown",
            support_status=LanguageSupportStatus.UNKNOWN.value,
            support_label="Unknown",
            confidence=0.0,
            message=message,
        )

    def _find_files(self, names: list[str]) -> list[str]:
        wanted = {n.lower() for n in names}
        found: list[str] = []
        for path in self._walk():
            if path.name.lower() in wanted:
                found.append(str(path.relative_to(self.repo_path)))
        return found

    def _find_files_by_suffix(self, suffixes: list[str]) -> list[str]:
        found: list[str] = []
        for path in self._walk():
            if any(path.name.endswith(s) for s in suffixes):
                found.append(str(path.relative_to(self.repo_path)))
        return found[:50]

    def _walk(self):
        if not self.repo_path.exists():
            return
        for path in self.repo_path.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel_parts = path.relative_to(self.repo_path).parts
            except ValueError:
                continue
            if any(p in _SKIP_DIRS for p in rel_parts[:-1]):
                continue
            yield path

    def _count_source_files(self, ext_map: dict[str, str]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for path in self._walk():
            lang = ext_map.get(path.suffix.lower())
            if lang:
                counts[lang] = counts.get(lang, 0) + 1
            if sum(counts.values()) > 5000:
                break
        return counts

    def _inspect_pyproject(self, path: Path, add_pm, add_fw, add_lang) -> None:
        try:
            import tomli

            data = tomli.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return
        if "tool" in data and "poetry" in (data.get("tool") or {}):
            add_pm("poetry")
        if data.get("project") or (data.get("tool") or {}).get("poetry"):
            add_lang("python", 1.0, "pyproject.toml project table")
        deps: dict[str, Any] = {}
        project = data.get("project") or {}
        for item in project.get("dependencies") or []:
            if isinstance(item, str):
                name = re.split(r"[<>=!~;\[]", item, maxsplit=1)[0].strip().lower()
                deps[name] = True
        poetry_deps = ((data.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
        if isinstance(poetry_deps, dict):
            for name in poetry_deps:
                deps[str(name).lower()] = True
        self._frameworks_from_dep_names(deps.keys(), add_fw)

    def _inspect_requirements(self, path: Path, add_fw) -> None:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return
        names = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            name = re.split(r"[<>=!~;\[]", line, maxsplit=1)[0].strip().lower()
            if name:
                names.append(name)
        self._frameworks_from_dep_names(names, add_fw)

    def _inspect_package_json(self, path: Path, add_fw, add_lang) -> None:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return
        deps = {}
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            block = data.get(key) or {}
            if isinstance(block, dict):
                deps.update({str(k).lower(): v for k, v in block.items()})
        if any(k.startswith("@types/") for k in deps) or path.with_name("tsconfig.json").exists():
            add_lang("typescript", 2.0, "typescript signals in package.json")
        mapping = {
            "next": "Next.js",
            "nuxt": "Nuxt",
            "react": "React",
            "vue": "Vue",
            "angular": "Angular",
            "express": "Express",
            "nestjs": "NestJS",
            "@nestjs/core": "NestJS",
            "svelte": "Svelte",
        }
        for pkg, fw in mapping.items():
            if pkg in deps:
                add_fw(fw)

    def _frameworks_from_dep_names(self, names, add_fw) -> None:
        mapping = {
            "django": "Django",
            "flask": "Flask",
            "fastapi": "FastAPI",
            "starlette": "Starlette",
            "tornado": "Tornado",
            "pyramid": "Pyramid",
            "celery": "Celery",
            "langchain": "LangChain",
            "streamlit": "Streamlit",
            "gradio": "Gradio",
        }
        for name in names:
            key = str(name).lower().replace("_", "-")
            if key in mapping:
                add_fw(mapping[key])

    def _primary_package_manager(self, language_id: str, managers: list[str]) -> Optional[str]:
        if not managers:
            return None
        preference = {
            "python": ["uv", "poetry", "pipenv", "pip", "setuptools"],
            "javascript": ["pnpm", "yarn", "bun", "npm"],
            "typescript": ["pnpm", "yarn", "bun", "npm"],
            "go": ["go modules"],
            "java": ["gradle", "maven"],
            "kotlin": ["gradle", "maven"],
            "php": ["composer"],
            "rust": ["cargo"],
            "ruby": ["bundler"],
            "csharp": ["nuget"],
        }.get(language_id, managers)
        for pref in preference:
            if pref in managers:
                return pref
        return managers[0]
