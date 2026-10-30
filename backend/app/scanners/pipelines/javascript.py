"""JavaScript and TypeScript scan pipeline.

Inventory, lockfile versions, import/require usage, graph, OSV, license, and
health are implemented. Dynamic Upgrade Intelligence covers this ecosystem
(deterministic evidence first, AI fallback). The Python catalog is an extra
deterministic source, not the architecture for other languages.
"""

from __future__ import annotations

from typing import Any

from app.scanners.analyzers.base import LanguageAnalyzer
from app.scanners.analyzers.javascript import JavaScriptAnalyzer
from app.scanners.pipelines.base import SupportedPipeline


class JavaScriptPipeline(SupportedPipeline):
    language_id = "javascript"
    display_name = "JavaScript / TypeScript"

    def get_analyzer(self) -> LanguageAnalyzer:
        return JavaScriptAnalyzer()

    def describe(self) -> dict[str, Any]:
        return {
            "language_id": self.language_id,
            "display_name": self.display_name,
            "support_status": self.support_status.value,
            "support_label": self.support_label,
            "implemented": True,
            "ecosystem": "npm",
            "capabilities": [
                "manifest_scan",
                "import_usage_index",
                "dependency_graph",
                "security_analysis",
                "license_analysis",
                "health_scoring",
            ],
            "upgrade_impact": "limited",
            "analyzer": "JavaScriptAnalyzer",
        }


class TypeScriptPipeline(JavaScriptPipeline):
    language_id = "typescript"
    display_name = "TypeScript / Node.js"
