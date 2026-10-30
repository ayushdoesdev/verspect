"""Python language pipeline — fully supported scan pipeline.

Manifest parsing, AST indexing, PyPI/OSV enrichment, health scoring, and the
deterministic upgrade catalog are executed by the Celery scan task for this
pipeline. Other languages use SupportedPipeline when an analyzer exists.
"""

from __future__ import annotations

from typing import Any

from app.scanners.analyzers.base import LanguageAnalyzer
from app.scanners.analyzers.python import PythonAnalyzer
from app.scanners.pipelines.base import FullySupportedPipeline


class PythonPipeline(FullySupportedPipeline):
    language_id = "python"
    display_name = "Python"

    def get_analyzer(self) -> LanguageAnalyzer:
        return PythonAnalyzer()

    def describe(self) -> dict[str, Any]:
        return {
            "language_id": self.language_id,
            "display_name": self.display_name,
            "support_status": self.support_status.value,
            "support_label": self.support_label,
            "implemented": True,
            "ecosystem": "PyPI",
            "capabilities": [
                "manifest_scan",
                "ast_usage_index",
                "dependency_graph",
                "security_analysis",
                "upgrade_simulator",
                "ai_migration_assistant",
            ],
            "analyzer": "PythonAnalyzer",
        }
