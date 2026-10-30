"""Dynamic Upgrade Intelligence — deterministic first, per-category AI fallback."""

from app.services.upgrade_intelligence.engine import DynamicUpgradeIntelligence
from app.services.upgrade_intelligence.models import IntelligenceReport

__all__ = ["DynamicUpgradeIntelligence", "IntelligenceReport"]
