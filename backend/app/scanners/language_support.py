"""Canonical language support depth.

The analyzer / pipeline registries are the source of truth. Stored
``support_status`` values from older scans (e.g. Node.js as ``coming_soon``)
must be remapped through this module — never trusted as current product state.
"""

from __future__ import annotations

from app.core.enums import LanguageSupportStatus

# Runtime / GitHub labels → analysis ecosystem ids.
LANGUAGE_ALIASES: dict[str, str] = {
    "js": "javascript",
    "javascript": "javascript",
    "node": "javascript",
    "nodejs": "javascript",
    "node.js": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "py": "python",
    "python": "python",
    "golang": "go",
    "go": "go",
    "java": "java",
    "rust": "rust",
    "php": "php",
    "ruby": "ruby",
    "rb": "ruby",
    "csharp": "csharp",
    "c#": "csharp",
    "kotlin": "kotlin",
}

# Analyzer exists AND Python-depth upgrade catalog / AST usage.
FULLY_SUPPORTED_LANGUAGE_IDS = frozenset({"python"})

# Analyzer exists; inventory, usage, OSV, license, health work.
# Dynamic Upgrade Intelligence covers all supported ecosystems
# (deterministic evidence first, per-category AI fallback).
# The Python migration catalog remains an additional deterministic source.
SUPPORTED_LANGUAGE_IDS = frozenset(
    {"javascript", "typescript", "go", "java", "rust", "php", "ruby"}
)

COMING_SOON_LANGUAGE_IDS = frozenset({"csharp", "kotlin"})

DISPLAY_NAMES: dict[str, str] = {
    "python": "Python",
    "javascript": "JavaScript / Node.js",
    "typescript": "TypeScript / Node.js",
    "go": "Go",
    "java": "Java",
    "rust": "Rust",
    "php": "PHP",
    "ruby": "Ruby",
    "csharp": "C#",
    "kotlin": "Kotlin",
}

_STATUS_LABELS = {
    LanguageSupportStatus.FULLY_SUPPORTED: "Fully Supported",
    LanguageSupportStatus.SUPPORTED: "Supported",
    LanguageSupportStatus.COMING_SOON: "Coming Soon",
    LanguageSupportStatus.UNKNOWN: "Unknown",
}


def normalize_language_id(language_id: str | None) -> str:
    raw = (language_id or "").strip().lower()
    if not raw:
        return "unknown"
    return LANGUAGE_ALIASES.get(raw, raw.replace(" ", ""))


def support_status_for_language(language_id: str | None) -> LanguageSupportStatus:
    lang = normalize_language_id(language_id)
    if lang in FULLY_SUPPORTED_LANGUAGE_IDS:
        return LanguageSupportStatus.FULLY_SUPPORTED
    if lang in SUPPORTED_LANGUAGE_IDS:
        return LanguageSupportStatus.SUPPORTED
    if lang in COMING_SOON_LANGUAGE_IDS:
        return LanguageSupportStatus.COMING_SOON
    return LanguageSupportStatus.UNKNOWN


def support_label_for(status: LanguageSupportStatus | str) -> str:
    if isinstance(status, str):
        try:
            status = LanguageSupportStatus(status)
        except ValueError:
            return status.replace("_", " ").title()
    return _STATUS_LABELS[status]


def display_name_for_language(language_id: str | None, fallback: str | None = None) -> str:
    lang = normalize_language_id(language_id)
    if lang in DISPLAY_NAMES:
        return DISPLAY_NAMES[lang]
    if fallback:
        return fallback
    if not lang or lang == "unknown":
        return "Unknown"
    return lang.replace("_", " ").title()


def language_is_analyzable(language_id: str | None) -> bool:
    status = support_status_for_language(language_id)
    return status in {
        LanguageSupportStatus.FULLY_SUPPORTED,
        LanguageSupportStatus.SUPPORTED,
    }


def canonicalize_support(
    *,
    language_id: str | None,
    support_status: str | None = None,
    support_label: str | None = None,
) -> tuple[str | None, str | None]:
    """Return (status, label) using the analyzer registry when language_id is known."""
    lang = normalize_language_id(language_id)
    if lang and lang != "unknown":
        status = support_status_for_language(lang)
        return status.value, support_label_for(status)
    if support_status and not support_label:
        return support_status, support_label_for(support_status)
    return support_status, support_label
