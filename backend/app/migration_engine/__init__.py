"""Universal Migration Intelligence Engine."""

from typing import TYPE_CHECKING

__all__ = ["MigrationEngine", "MigrationService", "LibraryRegistry", "SemanticASTIndex"]

if TYPE_CHECKING:
    from app.migration_engine.engine import MigrationEngine
    from app.migration_engine.migration_service import MigrationService
    from app.migration_engine.registry import LibraryRegistry
    from app.migration_engine.semantic_index import SemanticASTIndex


def __getattr__(name: str):
    if name == "MigrationEngine":
        from app.migration_engine.engine import MigrationEngine

        return MigrationEngine
    if name == "MigrationService":
        from app.migration_engine.migration_service import MigrationService

        return MigrationService
    if name == "LibraryRegistry":
        from app.migration_engine.registry import LibraryRegistry

        return LibraryRegistry
    if name == "SemanticASTIndex":
        from app.migration_engine.semantic_index import SemanticASTIndex

        return SemanticASTIndex
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
