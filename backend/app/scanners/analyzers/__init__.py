"""Resolve a LanguageAnalyzer for a language id or classification."""

from __future__ import annotations

from typing import Optional

from app.scanners.analyzers.base import LanguageAnalyzer
from app.scanners.analyzers.go import GoAnalyzer
from app.scanners.analyzers.java import JavaAnalyzer
from app.scanners.analyzers.javascript import JavaScriptAnalyzer
from app.scanners.analyzers.php import PHPAnalyzer
from app.scanners.analyzers.python import PythonAnalyzer
from app.scanners.analyzers.ruby import RubyAnalyzer
from app.scanners.analyzers.rust import RustAnalyzer
from app.scanners.classification import ClassificationResult
from app.scanners.language_support import normalize_language_id

ANALYZERS: dict[str, type[LanguageAnalyzer]] = {
    "python": PythonAnalyzer,
    "javascript": JavaScriptAnalyzer,
    "typescript": JavaScriptAnalyzer,
    "go": GoAnalyzer,
    "java": JavaAnalyzer,
    "rust": RustAnalyzer,
    "php": PHPAnalyzer,
    "ruby": RubyAnalyzer,
}


def get_analyzer(language_id: str) -> Optional[LanguageAnalyzer]:
    cls = ANALYZERS.get(normalize_language_id(language_id))
    return cls() if cls is not None else None


def get_analyzer_for_classification(
    classification: ClassificationResult,
) -> Optional[LanguageAnalyzer]:
    return get_analyzer(classification.language_id or "")


def list_analyzers() -> list[dict[str, str]]:
    return [
        {
            "language_id": "python",
            "display_name": "Python",
            "ecosystem": "PyPI",
            "status": "implemented",
        },
        {
            "language_id": "javascript",
            "display_name": "JavaScript / TypeScript",
            "ecosystem": "npm",
            "status": "implemented",
        },
        {
            "language_id": "go",
            "display_name": "Go",
            "ecosystem": "Go",
            "status": "implemented",
        },
        {
            "language_id": "java",
            "display_name": "Java",
            "ecosystem": "Maven",
            "status": "implemented",
        },
        {
            "language_id": "rust",
            "display_name": "Rust",
            "ecosystem": "crates.io",
            "status": "implemented",
        },
        {
            "language_id": "php",
            "display_name": "PHP",
            "ecosystem": "Packagist",
            "status": "implemented",
        },
        {
            "language_id": "ruby",
            "display_name": "Ruby",
            "ecosystem": "RubyGems",
            "status": "implemented",
        },
    ]
