"""Resolve a LanguagePipeline from classification results.

Add a new language by:
  1. Implementing SupportedPipeline or FullySupportedPipeline
  2. Registering it in SUPPORTED_PIPELINES
Unsupported detections automatically map to ComingSoonPipeline.
"""

from __future__ import annotations

from app.scanners.classification import ClassificationResult
from app.scanners.language_support import (
    display_name_for_language,
    normalize_language_id,
    support_label_for,
    support_status_for_language,
)
from app.scanners.pipelines.base import ComingSoonPipeline, LanguagePipeline
from app.scanners.pipelines.go import GoPipeline
from app.scanners.pipelines.java import JavaPipeline
from app.scanners.pipelines.javascript import JavaScriptPipeline, TypeScriptPipeline
from app.scanners.pipelines.php import PHPPipeline
from app.scanners.pipelines.python import PythonPipeline
from app.scanners.pipelines.ruby import RubyPipeline
from app.scanners.pipelines.rust import RustPipeline

# Only pipelines listed here run analysis. Do not register stubs as supported.
SUPPORTED_PIPELINES: dict[str, type[LanguagePipeline]] = {
    "python": PythonPipeline,
    "javascript": JavaScriptPipeline,
    "typescript": TypeScriptPipeline,
    "go": GoPipeline,
    "java": JavaPipeline,
    "rust": RustPipeline,
    "php": PHPPipeline,
    "ruby": RubyPipeline,
}


def get_pipeline(classification: ClassificationResult) -> LanguagePipeline:
    """Return the pipeline for a classification (supported or coming-soon)."""
    lang = normalize_language_id(classification.language_id)
    pipeline_cls = SUPPORTED_PIPELINES.get(lang)
    if pipeline_cls is not None:
        return pipeline_cls()
    display = (
        classification.language
        or display_name_for_language(lang, fallback=lang.replace("_", " ").title())
    )
    return ComingSoonPipeline(language_id=lang or "unknown", display_name=display)


def list_language_support() -> list[dict]:
    """Public catalog of language support for docs / settings."""
    rows = []
    for language_id in (
        "python",
        "javascript",
        "typescript",
        "go",
        "java",
        "php",
        "rust",
        "ruby",
    ):
        status = support_status_for_language(language_id)
        rows.append(
            {
                "language_id": language_id,
                "display_name": display_name_for_language(language_id),
                "support_status": status.value,
                "support_label": support_label_for(status),
            }
        )
    return rows
