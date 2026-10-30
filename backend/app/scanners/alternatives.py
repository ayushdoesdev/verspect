"""Built-in alternative library knowledge base + enrichment."""

from __future__ import annotations

from typing import Any

from app.core.enums import MigrationDifficulty
from app.scanners.normalize import normalize_package_name

# Curated alternatives for common Python packages
ALTERNATIVES_KB: dict[str, list[dict[str, Any]]] = {
    "pypdf2": [
        {
            "alternative_name": "pypdf",
            "reason": "pypdf is the actively maintained successor to PyPDF2 with the same API lineage.",
            "pros": ["Actively maintained", "Security fixes", "Compatible API", "Better performance"],
            "cons": ["May need import path updates", "Some edge-case API differences"],
            "migration_effort": MigrationDifficulty.LOW.value,
            "api_compatibility": 0.9,
        }
    ],
    "pycrypto": [
        {
            "alternative_name": "pycryptodome",
            "reason": "PyCrypto is unmaintained; PyCryptodome is a drop-in replacement with security fixes.",
            "pros": ["Drop-in compatible", "Actively maintained", "Security patches"],
            "cons": ["Package name change in requirements"],
            "migration_effort": MigrationDifficulty.TRIVIAL.value,
            "api_compatibility": 0.95,
        }
    ],
    "flask": [
        {
            "alternative_name": "fastapi",
            "reason": "FastAPI offers async support, automatic OpenAPI, and modern type-hint based validation.",
            "pros": ["Async", "Auto docs", "Pydantic validation", "High performance"],
            "cons": ["Different paradigm", "Rewrite routes", "Steeper migration"],
            "migration_effort": MigrationDifficulty.HIGH.value,
            "api_compatibility": 0.2,
        },
        {
            "alternative_name": "litestar",
            "reason": "Litestar is a modern ASGI framework with strong typing and plugin ecosystem.",
            "pros": ["ASGI", "Typed", "DI built-in"],
            "cons": ["Smaller community than FastAPI", "Full rewrite"],
            "migration_effort": MigrationDifficulty.HIGH.value,
            "api_compatibility": 0.15,
        },
    ],
    "requests": [
        {
            "alternative_name": "httpx",
            "reason": "HTTPX provides sync + async clients with a requests-compatible API.",
            "pros": ["Async support", "HTTP/2", "Familiar API", "Timeouts by default"],
            "cons": ["Slightly different session model", "Larger dependency tree"],
            "migration_effort": MigrationDifficulty.LOW.value,
            "api_compatibility": 0.85,
        }
    ],
    "django": [
        {
            "alternative_name": "fastapi",
            "reason": "For API-first apps, FastAPI is lighter and faster to iterate.",
            "pros": ["Lightweight", "Async", "Modern typing"],
            "cons": ["No batteries-included admin/ORM", "Major rewrite"],
            "migration_effort": MigrationDifficulty.VERY_HIGH.value,
            "api_compatibility": 0.05,
        }
    ],
    "pillow": [
        {
            "alternative_name": "pillow-simd",
            "reason": "SIMD-accelerated fork of Pillow for CPU-bound image processing.",
            "pros": ["Faster", "API compatible"],
            "cons": ["Platform wheel limitations"],
            "migration_effort": MigrationDifficulty.TRIVIAL.value,
            "api_compatibility": 0.98,
        }
    ],
    "pyyaml": [
        {
            "alternative_name": "ruamel.yaml",
            "reason": "ruamel.yaml preserves comments/ordering and has safer load defaults.",
            "pros": ["Round-trip YAML", "Safer loading", "Comment preservation"],
            "cons": ["Different API surface", "Heavier"],
            "migration_effort": MigrationDifficulty.MEDIUM.value,
            "api_compatibility": 0.5,
        }
    ],
    "boto": [
        {
            "alternative_name": "boto3",
            "reason": "boto is deprecated; boto3 is the official AWS SDK for Python.",
            "pros": ["Official", "Maintained", "Full AWS coverage"],
            "cons": ["API is different from boto"],
            "migration_effort": MigrationDifficulty.HIGH.value,
            "api_compatibility": 0.3,
        }
    ],
    "nose": [
        {
            "alternative_name": "pytest",
            "reason": "nose is unmaintained; pytest is the modern standard test runner.",
            "pros": ["Active ecosystem", "Fixtures", "Plugins"],
            "cons": ["Some assertion/style changes"],
            "migration_effort": MigrationDifficulty.MEDIUM.value,
            "api_compatibility": 0.6,
        }
    ],
    "mock": [
        {
            "alternative_name": "unittest.mock",
            "reason": "mock was merged into the standard library as unittest.mock.",
            "pros": ["stdlib", "No dependency"],
            "cons": ["Import path change"],
            "migration_effort": MigrationDifficulty.TRIVIAL.value,
            "api_compatibility": 0.99,
        }
    ],
}


class AlternativeEngine:
    def suggest(self, package_name: str) -> list[dict[str, Any]]:
        key = normalize_package_name(package_name)
        entries = ALTERNATIVES_KB.get(key, [])
        results = []
        for i, entry in enumerate(entries, start=1):
            results.append(
                {
                    "package_name": package_name,
                    "alternative_name": entry["alternative_name"],
                    "alternative_normalized": normalize_package_name(entry["alternative_name"]),
                    "reason": entry["reason"],
                    "pros": entry.get("pros", []),
                    "cons": entry.get("cons", []),
                    "migration_effort": entry.get(
                        "migration_effort", MigrationDifficulty.MEDIUM.value
                    ),
                    "api_compatibility": entry.get("api_compatibility"),
                    "rank": i,
                    "confidence": 0.9,
                    "source": "knowledge_base",
                }
            )
        return results
