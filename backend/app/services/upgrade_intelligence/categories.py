"""The 30 upgrade-analysis categories.

Each category is answered independently. A missing deterministic result in one
category must never collapse the entire report to Unknown.
"""

from __future__ import annotations

from typing import Literal

CategoryId = Literal[
    "what_changed",
    "breaking_changes",
    "removed_apis",
    "renamed_apis",
    "changed_apis",
    "changed_signatures",
    "changed_types",
    "changed_modules",
    "changed_configuration",
    "changed_defaults",
    "deprecated_functionality",
    "security_relevant_changes",
    "affected_dependencies",
    "affected_apis_used",
    "affected_files",
    "affected_lines",
    "why_file_affected",
    "required_code_changes",
    "required_configuration_changes",
    "migration_rules",
    "migration_steps",
    "upgrade_risk",
    "confidence",
    "evidence",
    "sources",
    "recommended_target_version",
    "migration_required",
    "upgrade_appears_safe",
    "upgrade_potentially_breaking",
    "upgrade_verified_breaking",
]

CATEGORY_IDS: tuple[CategoryId, ...] = (
    "what_changed",
    "breaking_changes",
    "removed_apis",
    "renamed_apis",
    "changed_apis",
    "changed_signatures",
    "changed_types",
    "changed_modules",
    "changed_configuration",
    "changed_defaults",
    "deprecated_functionality",
    "security_relevant_changes",
    "affected_dependencies",
    "affected_apis_used",
    "affected_files",
    "affected_lines",
    "why_file_affected",
    "required_code_changes",
    "required_configuration_changes",
    "migration_rules",
    "migration_steps",
    "upgrade_risk",
    "confidence",
    "evidence",
    "sources",
    "recommended_target_version",
    "migration_required",
    "upgrade_appears_safe",
    "upgrade_potentially_breaking",
    "upgrade_verified_breaking",
)

CATEGORY_TITLES: dict[CategoryId, str] = {
    "what_changed": "What changed",
    "breaking_changes": "Breaking changes",
    "removed_apis": "Removed APIs",
    "renamed_apis": "Renamed APIs",
    "changed_apis": "Changed APIs",
    "changed_signatures": "Changed function/method signatures",
    "changed_types": "Changed types/interfaces",
    "changed_modules": "Changed modules/imports",
    "changed_configuration": "Changed configuration",
    "changed_defaults": "Changed defaults/behavior",
    "deprecated_functionality": "Deprecated functionality",
    "security_relevant_changes": "Security-relevant changes",
    "affected_dependencies": "Affected dependencies",
    "affected_apis_used": "Affected APIs used by this repository",
    "affected_files": "Affected files",
    "affected_lines": "Affected lines",
    "why_file_affected": "Why each file is affected",
    "required_code_changes": "Required code changes",
    "required_configuration_changes": "Required configuration changes",
    "migration_rules": "Migration rules",
    "migration_steps": "Migration steps",
    "upgrade_risk": "Upgrade risk",
    "confidence": "Confidence",
    "evidence": "Evidence",
    "sources": "Sources",
    "recommended_target_version": "Recommended target version",
    "migration_required": "Whether migration is required",
    "upgrade_appears_safe": "Whether the upgrade appears safe",
    "upgrade_potentially_breaking": "Whether the upgrade is potentially breaking",
    "upgrade_verified_breaking": "Whether the upgrade is verified breaking",
}

# Categories that repository usage can often complete without a package catalog.
USAGE_BACKED_CATEGORIES: frozenset[CategoryId] = frozenset(
    {
        "affected_apis_used",
        "affected_files",
        "affected_lines",
        "why_file_affected",
        "sources",
        "evidence",
        "recommended_target_version",
        "confidence",
    }
)

# Categories that typically need changelog/docs/AI when no catalog exists.
DOC_BACKED_CATEGORIES: frozenset[CategoryId] = frozenset(
    {
        "what_changed",
        "breaking_changes",
        "removed_apis",
        "renamed_apis",
        "changed_apis",
        "changed_signatures",
        "changed_types",
        "changed_modules",
        "changed_configuration",
        "changed_defaults",
        "deprecated_functionality",
        "security_relevant_changes",
        "affected_dependencies",
        "required_code_changes",
        "required_configuration_changes",
        "migration_rules",
        "migration_steps",
    }
)
