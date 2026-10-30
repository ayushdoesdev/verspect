"""Fully supported Rust Cargo scan pipeline."""

from __future__ import annotations

from typing import Any

from app.scanners.analyzers.base import LanguageAnalyzer
from app.scanners.analyzers.rust import RustAnalyzer
from app.scanners.pipelines.base import SupportedPipeline


class RustPipeline(SupportedPipeline):
    language_id = "rust"
    display_name = "Rust"

    def get_analyzer(self) -> LanguageAnalyzer:
        return RustAnalyzer()

    def describe(self) -> dict[str, Any]:
        return {
            "language_id": self.language_id,
            "display_name": self.display_name,
            "support_status": self.support_status.value,
            "support_label": self.support_label,
            "implemented": True,
            "ecosystem": "crates.io",
            "capabilities": [
                "manifest_scan",
                "import_usage_index",
                "dependency_graph",
                "security_analysis",
                "upgrade_simulator",
                "ai_migration_assistant",
            ],
            "analyzer": "RustAnalyzer",
        }
