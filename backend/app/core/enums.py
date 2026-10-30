"""Application-wide enums."""

import enum


class ScanStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    CLONING = "cloning"
    CLASSIFYING = "classifying"
    SCANNING_MANIFESTS = "scanning_manifests"
    PARSING_AST = "parsing_ast"
    CHECKING_VERSIONS = "checking_versions"
    CHECKING_VULNERABILITIES = "checking_vulnerabilities"
    CHECKING_LICENSES = "checking_licenses"
    SCORING_HEALTH = "scoring_health"
    ANALYZING_AI = "analyzing_ai"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LanguageSupportStatus(str, enum.Enum):
    """Repository language support level.

    fully_supported — analyzer plus deeper ecosystem intelligence (Python today).
    supported — analyzer exists and real inventory/usage/OSV/license/health work.
    coming_soon — detected ecosystem with no implemented analyzer.
    unknown — could not classify.
    """

    FULLY_SUPPORTED = "fully_supported"
    SUPPORTED = "supported"
    COMING_SOON = "coming_soon"
    UNKNOWN = "unknown"


class ScanType(str, enum.Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    WEBHOOK = "webhook"
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    # Independent post-scan AI Upgrade Advisor job (never blocks Repository Scan)
    AI_ADVISOR = "ai_advisor"


class AlertSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertType(str, enum.Enum):
    CVE = "cve"
    LICENSE_VIOLATION = "license_violation"
    LICENSE_WARNING = "license_warning"
    BREAKING_RELEASE = "breaking_release"
    OUTDATED = "outdated"
    HEALTH_DEGRADED = "health_degraded"
    DEPRECATED_API = "deprecated_api"
    MAJOR_RELEASE = "major_release"


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class DependencyStatus(str, enum.Enum):
    UP_TO_DATE = "up_to_date"
    OUTDATED = "outdated"
    VULNERABLE = "vulnerable"
    LICENSE_ISSUE = "license_issue"
    UNKNOWN = "unknown"
    ABANDONED = "abandoned"


class LicensePolicyAction(str, enum.Enum):
    ALLOW = "allow"
    WARN = "warn"
    REJECT = "reject"


class MigrationDifficulty(str, enum.Enum):
    TRIVIAL = "trivial"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    SLACK = "slack"


class RepositorySyncStatus(str, enum.Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    ERROR = "error"
    NEVER_SYNCED = "never_synced"


class UsageKind(str, enum.Enum):
    IMPORT = "import"
    FROM_IMPORT = "from_import"
    FUNCTION_CALL = "function_call"
    METHOD_CALL = "method_call"
    CLASS_INSTANTIATION = "class_instantiation"
    DECORATOR = "decorator"
    INHERITANCE = "inheritance"
    CONTEXT_MANAGER = "context_manager"
    TYPE_HINT = "type_hint"
    ATTRIBUTE = "attribute"
    KEYWORD_ARGUMENT = "keyword_argument"
    ASSIGNMENT = "assignment"


class SimulationStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    COLLECTING_SOURCES = "collecting_sources"
    ANALYZING_IMPACT = "analyzing_impact"
    GENERATING_PLAN = "generating_plan"
    SCORING = "scoring"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
