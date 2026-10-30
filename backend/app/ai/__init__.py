"""AI package — provider-agnostic Dependency Intelligence LLM layer."""

from app.ai.analyzer import AIAnalyzer
from app.ai.service import AIService
from app.ai.upgrade_simulator import UpgradeImpactAnalyzer

__all__ = ["AIService", "AIAnalyzer", "UpgradeImpactAnalyzer"]
