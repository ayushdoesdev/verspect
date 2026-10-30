"""Structured migration rule catalog — deterministic, version-range keyed.

Rules are not invented by AI. Seeded from official migration guides.
New libraries can add entries here or via the knowledge base after
docs-only extraction (never from security advisories).
"""

from __future__ import annotations

from typing import Optional

from packaging.version import InvalidVersion, Version

from app.migration_engine.models import MigrationRuleDTO
from app.scanners.normalize import normalize_package_name


def _v(value: str) -> Optional[Version]:
    try:
        return Version(str(value).lstrip("v"))
    except InvalidVersion:
        return None


def version_crosses(
    from_version: str,
    to_version: str,
    *,
    threshold: str,
) -> bool:
    """True when from < threshold <= to (major upgrade crossing threshold)."""
    lo, hi, th = _v(from_version), _v(to_version), _v(threshold)
    if not lo or not hi or not th:
        # Fallback: string compare for "1" / "2" style
        try:
            return float(from_version.split(".")[0]) < float(threshold.split(".")[0]) <= float(
                to_version.split(".")[0]
            )
        except Exception:
            return False
    return lo < th <= hi


def _rule(**kwargs) -> MigrationRuleDTO:
    return MigrationRuleDTO.model_validate(kwargs)


# ---------------------------------------------------------------------------
# Official structured rules (library-agnostic schema, seeded content)
# ---------------------------------------------------------------------------

PYDANTIC_V1_TO_V2: list[dict] = [
    {
        "library": "pydantic",
        "symbol": "validator",
        "match_kind": "decorator",
        "kind": "renamed",
        "description": "Deprecated in Pydantic v2. Use @field_validator instead of @validator.",
        "severity": "high",
        "confidence": 0.99,
        "before": "@validator",
        "after": "@field_validator",
        "reason": "Deprecated in Pydantic v2.",
        "official_reference": "https://docs.pydantic.dev/latest/migration/",
        "reference_title": "Pydantic V2 Migration Guide",
        "auto_fixable": True,
        "estimated_effort": "low",
        "source_type": "migration_guide",
        "source_url": "https://docs.pydantic.dev/latest/migration/",
        "import_fix": {
            "remove": ["validator"],
            "add": ["field_validator"],
            "module": "pydantic",
        },
        "unchanged": False,
    },
    {
        "library": "pydantic",
        "symbol": "root_validator",
        "match_kind": "decorator",
        "kind": "renamed",
        "description": "Deprecated in Pydantic v2. Use @model_validator instead of @root_validator.",
        "severity": "high",
        "confidence": 0.99,
        "before": "@root_validator",
        "after": "@model_validator",
        "reason": "Deprecated in Pydantic v2.",
        "official_reference": "https://docs.pydantic.dev/latest/migration/",
        "reference_title": "Pydantic V2 Migration Guide",
        "auto_fixable": True,
        "estimated_effort": "medium",
        "source_type": "migration_guide",
        "source_url": "https://docs.pydantic.dev/latest/migration/",
        "import_fix": {
            "remove": ["root_validator"],
            "add": ["model_validator"],
            "module": "pydantic",
        },
        "unchanged": False,
    },
    {
        "library": "pydantic",
        "symbol": "BaseModel",
        "match_kind": "import",
        "kind": "behavior_change",
        "description": "BaseModel remains the primary model base in Pydantic v2.",
        "severity": "info",
        "confidence": 1.0,
        "before": None,
        "after": None,
        "reason": "No migration required for BaseModel itself.",
        "official_reference": "https://docs.pydantic.dev/latest/migration/",
        "reference_title": "Pydantic V2 Migration Guide",
        "auto_fixable": False,
        "estimated_effort": "trivial",
        "source_type": "migration_guide",
        "source_url": "https://docs.pydantic.dev/latest/migration/",
        "unchanged": True,
    },
    {
        "library": "pydantic",
        "symbol": "BaseModel",
        "match_kind": "inheritance",
        "kind": "behavior_change",
        "description": "Inheriting from BaseModel is still valid in Pydantic v2.",
        "severity": "info",
        "confidence": 1.0,
        "before": None,
        "after": None,
        "reason": "No migration required for BaseModel inheritance.",
        "official_reference": "https://docs.pydantic.dev/latest/migration/",
        "reference_title": "Pydantic V2 Migration Guide",
        "auto_fixable": False,
        "estimated_effort": "trivial",
        "source_type": "migration_guide",
        "source_url": "https://docs.pydantic.dev/latest/migration/",
        "unchanged": True,
    },
    {
        "library": "pydantic",
        "symbol": "Config",
        "match_kind": "attribute",
        "kind": "renamed",
        "description": "Inner Config class is replaced by model_config = ConfigDict(...) in Pydantic v2.",
        "severity": "medium",
        "confidence": 0.85,
        "before": "class Config:",
        "after": "model_config = ConfigDict(",
        "reason": "Config class deprecated in Pydantic v2.",
        "official_reference": "https://docs.pydantic.dev/latest/migration/",
        "reference_title": "Pydantic V2 Migration Guide",
        "auto_fixable": False,
        "estimated_effort": "medium",
        "source_type": "migration_guide",
        "source_url": "https://docs.pydantic.dev/latest/migration/",
        "unchanged": False,
    },
    {
        "library": "pydantic",
        "symbol": ".dict",
        "match_kind": "method_call",
        "kind": "renamed",
        "description": "model.dict() is replaced by model.model_dump() in Pydantic v2.",
        "severity": "high",
        "confidence": 0.95,
        "before": ".dict(",
        "after": ".model_dump(",
        "reason": "Deprecated in Pydantic v2.",
        "official_reference": "https://docs.pydantic.dev/latest/migration/",
        "reference_title": "Pydantic V2 Migration Guide",
        "auto_fixable": True,
        "estimated_effort": "low",
        "source_type": "migration_guide",
        "source_url": "https://docs.pydantic.dev/latest/migration/",
        "unchanged": False,
    },
    {
        "library": "pydantic",
        "symbol": ".json",
        "match_kind": "method_call",
        "kind": "renamed",
        "description": "model.json() is replaced by model.model_dump_json() in Pydantic v2.",
        "severity": "high",
        "confidence": 0.95,
        "before": ".json(",
        "after": ".model_dump_json(",
        "reason": "Deprecated in Pydantic v2.",
        "official_reference": "https://docs.pydantic.dev/latest/migration/",
        "reference_title": "Pydantic V2 Migration Guide",
        "auto_fixable": True,
        "estimated_effort": "low",
        "source_type": "migration_guide",
        "source_url": "https://docs.pydantic.dev/latest/migration/",
        "unchanged": False,
    },
    {
        "library": "pydantic",
        "symbol": "parse_obj",
        "match_kind": "method_call",
        "kind": "renamed",
        "description": "parse_obj is replaced by model_validate in Pydantic v2.",
        "severity": "high",
        "confidence": 0.95,
        "before": "parse_obj",
        "after": "model_validate",
        "reason": "Deprecated in Pydantic v2.",
        "official_reference": "https://docs.pydantic.dev/latest/migration/",
        "reference_title": "Pydantic V2 Migration Guide",
        "auto_fixable": True,
        "estimated_effort": "low",
        "source_type": "migration_guide",
        "source_url": "https://docs.pydantic.dev/latest/migration/",
        "unchanged": False,
    },
]


# NumPy 2.0 removed Python-builtin alias names on the numpy namespace.
# Official: https://numpy.org/devdocs/numpy_2_0_migration_guide.html
NUMPY_1_TO_2_ALIASES: list[dict] = [
    {
        "library": "numpy",
        "symbol": "float",
        "match_kind": "attribute",
        "kind": "removed",
        "description": "np.float was removed in NumPy 2.0. Use the builtin float instead.",
        "severity": "high",
        "confidence": 0.99,
        "before": "np.float",
        "after": "float",
        "reason": "Removed in NumPy 2.0 — replace with builtin float (or np.float64).",
        "official_reference": "https://numpy.org/devdocs/numpy_2_0_migration_guide.html",
        "reference_title": "NumPy 2.0 Migration Guide",
        "auto_fixable": True,
        "estimated_effort": "trivial",
        "source_type": "migration_guide",
        "source_url": "https://numpy.org/devdocs/numpy_2_0_migration_guide.html",
        "unchanged": False,
    },
    {
        "library": "numpy",
        "symbol": "int",
        "match_kind": "attribute",
        "kind": "removed",
        "description": "np.int was removed in NumPy 2.0. Use the builtin int instead.",
        "severity": "high",
        "confidence": 0.99,
        "before": "np.int",
        "after": "int",
        "reason": "Removed in NumPy 2.0 — replace with builtin int (or np.int_).",
        "official_reference": "https://numpy.org/devdocs/numpy_2_0_migration_guide.html",
        "reference_title": "NumPy 2.0 Migration Guide",
        "auto_fixable": True,
        "estimated_effort": "trivial",
        "source_type": "migration_guide",
        "source_url": "https://numpy.org/devdocs/numpy_2_0_migration_guide.html",
        "unchanged": False,
    },
    {
        "library": "numpy",
        "symbol": "bool",
        "match_kind": "attribute",
        "kind": "removed",
        "description": "np.bool was removed in NumPy 2.0. Use the builtin bool instead.",
        "severity": "high",
        "confidence": 0.99,
        "before": "np.bool",
        "after": "bool",
        "reason": "Removed in NumPy 2.0 — replace with builtin bool (or np.bool_).",
        "official_reference": "https://numpy.org/devdocs/numpy_2_0_migration_guide.html",
        "reference_title": "NumPy 2.0 Migration Guide",
        "auto_fixable": True,
        "estimated_effort": "trivial",
        "source_type": "migration_guide",
        "source_url": "https://numpy.org/devdocs/numpy_2_0_migration_guide.html",
        "unchanged": False,
    },
    {
        "library": "numpy",
        "symbol": "object",
        "match_kind": "attribute",
        "kind": "removed",
        "description": "np.object was removed in NumPy 2.0. Use the builtin object instead.",
        "severity": "high",
        "confidence": 0.99,
        "before": "np.object",
        "after": "object",
        "reason": "Removed in NumPy 2.0 — replace with builtin object (or np.object_).",
        "official_reference": "https://numpy.org/devdocs/numpy_2_0_migration_guide.html",
        "reference_title": "NumPy 2.0 Migration Guide",
        "auto_fixable": True,
        "estimated_effort": "trivial",
        "source_type": "migration_guide",
        "source_url": "https://numpy.org/devdocs/numpy_2_0_migration_guide.html",
        "unchanged": False,
    },
    {
        "library": "numpy",
        "symbol": "complex",
        "match_kind": "attribute",
        "kind": "removed",
        "description": "np.complex was removed in NumPy 2.0. Use the builtin complex instead.",
        "severity": "high",
        "confidence": 0.99,
        "before": "np.complex",
        "after": "complex",
        "reason": "Removed in NumPy 2.0 — replace with builtin complex (or np.complex128).",
        "official_reference": "https://numpy.org/devdocs/numpy_2_0_migration_guide.html",
        "reference_title": "NumPy 2.0 Migration Guide",
        "auto_fixable": True,
        "estimated_effort": "trivial",
        "source_type": "migration_guide",
        "source_url": "https://numpy.org/devdocs/numpy_2_0_migration_guide.html",
        "unchanged": False,
    },
]


# FastAPI — on_event deprecated in favor of lifespan (0.93+ / documented migration).
# Official: https://fastapi.tiangolo.com/advanced/events/
FASTAPI_ON_EVENT_TO_LIFESPAN: list[dict] = [
    {
        "library": "fastapi",
        "symbol": "on_event",
        "match_kind": "method_call",
        "kind": "deprecated",
        "description": (
            "app.on_event() is deprecated. Prefer lifespan context managers "
            "(@asynccontextmanager) for startup/shutdown."
        ),
        "severity": "medium",
        "confidence": 0.9,
        "before": '@app.on_event("startup")',
        "after": "lifespan=...",
        "reason": "Deprecated FastAPI event hooks — migrate to lifespan.",
        "official_reference": "https://fastapi.tiangolo.com/advanced/events/",
        "reference_title": "FastAPI — Lifespan Events",
        "auto_fixable": False,
        "estimated_effort": "medium",
        "source_type": "migration_guide",
        "source_url": "https://fastapi.tiangolo.com/advanced/events/",
        "unchanged": False,
    },
    {
        "library": "fastapi",
        "symbol": "FastAPI",
        "match_kind": "import",
        "kind": "behavior_change",
        "description": "FastAPI application class remains the primary entrypoint.",
        "severity": "info",
        "confidence": 1.0,
        "before": None,
        "after": None,
        "reason": "No migration required for FastAPI class itself.",
        "official_reference": "https://fastapi.tiangolo.com/",
        "reference_title": "FastAPI Documentation",
        "auto_fixable": False,
        "estimated_effort": "trivial",
        "source_type": "docs",
        "source_url": "https://fastapi.tiangolo.com/",
        "unchanged": True,
    },
    {
        "library": "fastapi",
        "symbol": "BackgroundTasks",
        "match_kind": "import",
        "kind": "behavior_change",
        "description": "BackgroundTasks remains supported for in-process background work.",
        "severity": "info",
        "confidence": 1.0,
        "before": None,
        "after": None,
        "reason": "No migration required for BackgroundTasks itself.",
        "official_reference": "https://fastapi.tiangolo.com/tutorial/background-tasks/",
        "reference_title": "FastAPI — Background Tasks",
        "auto_fixable": False,
        "estimated_effort": "trivial",
        "source_type": "docs",
        "source_url": "https://fastapi.tiangolo.com/tutorial/background-tasks/",
        "unchanged": True,
    },
]


# Flask — before_first_request removed in 2.3
# Official: https://flask.palletsprojects.com/en/stable/changes/
FLASK_2_3_REMOVED: list[dict] = [
    {
        "library": "flask",
        "symbol": "before_first_request",
        "match_kind": "method_call",
        "kind": "removed",
        "description": (
            "Flask.before_first_request was removed in Flask 2.3. "
            "Use an application factory pattern or run setup code at import / lifespan time."
        ),
        "severity": "high",
        "confidence": 0.95,
        "before": "@app.before_first_request",
        "after": None,
        "reason": "Removed API — migrate off before_first_request.",
        "official_reference": "https://flask.palletsprojects.com/en/stable/changes/#version-2-3-0",
        "reference_title": "Flask 2.3 Changelog",
        "auto_fixable": False,
        "estimated_effort": "medium",
        "source_type": "changelog",
        "source_url": "https://flask.palletsprojects.com/en/stable/changes/#version-2-3-0",
        "unchanged": False,
    },
]


# Django — ugettext / ugettext_lazy removed in Django 4.0
# Official: https://docs.djangoproject.com/en/stable/releases/4.0/
DJANGO_4_REMOVED: list[dict] = [
    {
        "library": "django",
        "symbol": "ugettext",
        "match_kind": "import",
        "kind": "removed",
        "description": "django.utils.translation.ugettext was removed in Django 4.0. Use gettext.",
        "severity": "high",
        "confidence": 0.95,
        "before": "from django.utils.translation import ugettext",
        "after": "from django.utils.translation import gettext",
        "reason": "Removed unicode alias — use gettext.",
        "official_reference": "https://docs.djangoproject.com/en/stable/releases/4.0/#features-removed-in-4-0",
        "reference_title": "Django 4.0 Release Notes",
        "auto_fixable": True,
        "estimated_effort": "trivial",
        "source_type": "migration_guide",
        "source_url": "https://docs.djangoproject.com/en/stable/releases/4.0/",
        "unchanged": False,
    },
    {
        "library": "django",
        "symbol": "ugettext_lazy",
        "match_kind": "import",
        "kind": "removed",
        "description": (
            "django.utils.translation.ugettext_lazy was removed in Django 4.0. "
            "Use gettext_lazy."
        ),
        "severity": "high",
        "confidence": 0.95,
        "before": "from django.utils.translation import ugettext_lazy",
        "after": "from django.utils.translation import gettext_lazy",
        "reason": "Removed unicode alias — use gettext_lazy.",
        "official_reference": "https://docs.djangoproject.com/en/stable/releases/4.0/#features-removed-in-4-0",
        "reference_title": "Django 4.0 Release Notes",
        "auto_fixable": True,
        "estimated_effort": "trivial",
        "source_type": "migration_guide",
        "source_url": "https://docs.djangoproject.com/en/stable/releases/4.0/",
        "unchanged": False,
    },
]


CATALOG: dict[str, list[tuple[str, list[dict]]]] = {
    # package → list of (threshold_version, rules)
    "pydantic": [("2.0.0", PYDANTIC_V1_TO_V2)],
    "numpy": [("2.0.0", NUMPY_1_TO_2_ALIASES)],
    # on_event deprecation applies when upgrading across 0.93.0+
    "fastapi": [("0.93.0", FASTAPI_ON_EVENT_TO_LIFESPAN)],
    "flask": [("2.3.0", FLASK_2_3_REMOVED)],
    "django": [("4.0.0", DJANGO_4_REMOVED)],
}


def rules_for_upgrade(
    package_name: str,
    from_version: str,
    to_version: str,
) -> list[MigrationRuleDTO]:
    """Return structured catalog rules that apply to this version range."""
    key = normalize_package_name(package_name)
    entries = CATALOG.get(key, [])
    out: list[MigrationRuleDTO] = []
    for threshold, raw_rules in entries:
        if not version_crosses(from_version, to_version, threshold=threshold):
            continue
        for raw in raw_rules:
            data = {
                **raw,
                "from_version": from_version,
                "to_version": to_version,
                "validation_status": "validated",
            }
            out.append(_rule(**data))
    return out


def official_references_for(package_name: str) -> list[dict[str, str]]:
    """Unique titled migration references for a package."""
    key = normalize_package_name(package_name)
    if key == "pydantic":
        return [
            {
                "title": "Pydantic V2 Migration Guide",
                "url": "https://docs.pydantic.dev/latest/migration/",
                "source_type": "migration_guide",
            },
            {
                "title": "Pydantic Documentation",
                "url": "https://docs.pydantic.dev/",
                "source_type": "docs",
            },
            {
                "title": "PyPI — pydantic",
                "url": "https://pypi.org/project/pydantic/",
                "source_type": "pypi",
            },
        ]
    if key == "numpy":
        return [
            {
                "title": "NumPy 2.0 Migration Guide",
                "url": "https://numpy.org/devdocs/numpy_2_0_migration_guide.html",
                "source_type": "migration_guide",
            },
            {
                "title": "PyPI — numpy",
                "url": "https://pypi.org/project/numpy/",
                "source_type": "pypi",
            },
        ]
    if key == "fastapi":
        return [
            {
                "title": "FastAPI — Lifespan Events",
                "url": "https://fastapi.tiangolo.com/advanced/events/",
                "source_type": "migration_guide",
            },
            {
                "title": "PyPI — fastapi",
                "url": "https://pypi.org/project/fastapi/",
                "source_type": "pypi",
            },
        ]
    if key == "flask":
        return [
            {
                "title": "Flask 2.3 Changelog",
                "url": "https://flask.palletsprojects.com/en/stable/changes/#version-2-3-0",
                "source_type": "changelog",
            },
            {
                "title": "PyPI — flask",
                "url": "https://pypi.org/project/flask/",
                "source_type": "pypi",
            },
        ]
    if key == "django":
        return [
            {
                "title": "Django 4.0 Release Notes",
                "url": "https://docs.djangoproject.com/en/stable/releases/4.0/",
                "source_type": "migration_guide",
            },
            {
                "title": "PyPI — django",
                "url": "https://pypi.org/project/django/",
                "source_type": "pypi",
            },
        ]
    return [
        {
            "title": f"PyPI — {package_name}",
            "url": f"https://pypi.org/project/{key}/",
            "source_type": "pypi",
        }
    ]
