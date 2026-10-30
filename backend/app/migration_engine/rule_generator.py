"""AI rule generator — extracts structured MigrationRules from documentation.

AI grounds output in official docs/release notes. Never invents replacements.
Works for ANY Python library — no framework-specific logic.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import ValidationError

from app.ai.analyzer import AIAnalyzer
from app.ai.prompts import PromptTemplates
from app.core.logging import get_logger
from app.migration_engine.models import MigrationRuleBatch, MigrationRuleDTO

logger = get_logger(__name__)


class RuleGenerator:
    def __init__(
        self,
        ai: Optional[AIAnalyzer] = None,
        *,
        allow_ai: bool = True,
    ) -> None:
        """When ``allow_ai`` is False (Evaluation/Starter), never call an LLM."""
        from app.ai.analyzer import DisabledAIAnalyzer

        self.allow_ai = allow_ai
        if allow_ai:
            self.ai = ai if ai is not None else AIAnalyzer()
        else:
            # Locked AI is a valid handle with available=False — never None.
            self.ai = ai if ai is not None else DisabledAIAnalyzer()

    def generate(
        self,
        *,
        library: str,
        from_version: str,
        to_version: str,
        documentation_excerpts: list[dict[str, Any]],
        release_notes: list[dict[str, Any]],
    ) -> MigrationRuleBatch:
        payload = {
            "library": library,
            "from_version": from_version,
            "to_version": to_version,
            "documentation": [
                {
                    "source_type": d.get("source_type"),
                    "url": d.get("url"),
                    "title": d.get("title"),
                    "content": (d.get("content") or "")[:8000],
                }
                for d in documentation_excerpts[:8]
            ],
            "release_notes": [
                {
                    "version": r.get("version"),
                    "url": r.get("url"),
                    "title": r.get("title"),
                    "body": (r.get("body") or "")[:8000],
                }
                for r in release_notes[:15]
            ],
            "output_schema": {
                "summary": "string",
                "official_references": ["url"],
                "rules": [
                    {
                        "library": library,
                        "from_version": from_version,
                        "to_version": to_version,
                        "symbol": "str",
                        "kind": "removed|deprecated|renamed|signature_change|behavior_change|import_path_change|security|performance|added",
                        "description": "str",
                        "severity": "critical|high|medium|low|info",
                        "confidence": 0.0,
                        "before": "str|null",
                        "after": "str|null",
                        "reason": "str",
                        "official_reference": "url|null",
                        "auto_fixable": False,
                        "estimated_effort": "trivial|low|medium|high|very_high",
                        "source_type": "str",
                        "source_url": "url|null",
                    }
                ],
            },
        }

        if not self.allow_ai or not self.ai.available:
            return self._heuristic_extract(
                library, from_version, to_version, documentation_excerpts, release_notes
            )

        raw = self.ai._respond_json(
            PromptTemplates.migration_rules_system(),
            PromptTemplates.migration_rules_user(payload),
        )
        return self._validate_batch(raw, library, from_version, to_version, documentation_excerpts, release_notes)

    def _validate_batch(
        self,
        raw: dict[str, Any],
        library: str,
        from_version: str,
        to_version: str,
        docs: list[dict[str, Any]],
        releases: list[dict[str, Any]],
    ) -> MigrationRuleBatch:
        try:
            # Normalize rules
            rules_raw = raw.get("rules") or []
            normalized = []
            for r in rules_raw:
                if not isinstance(r, dict):
                    continue
                r.setdefault("library", library)
                r.setdefault("from_version", from_version)
                r.setdefault("to_version", to_version)
                if not r.get("symbol") or not r.get("description"):
                    continue
                # Reject invented replacements without reference when auto_fixable
                if r.get("auto_fixable") and not r.get("after"):
                    r["auto_fixable"] = False
                if r.get("auto_fixable") and not (r.get("official_reference") or r.get("source_url")):
                    r["auto_fixable"] = False
                    r["confidence"] = min(float(r.get("confidence") or 0.5), 0.6)
                normalized.append(r)
            raw["rules"] = normalized
            return MigrationRuleBatch.model_validate(raw)
        except ValidationError as exc:
            logger.warning("rule_batch_validation_failed", error=str(exc))
            return self._heuristic_extract(library, from_version, to_version, docs, releases)

    def _heuristic_extract(
        self,
        library: str,
        from_version: str,
        to_version: str,
        docs: list[dict[str, Any]],
        releases: list[dict[str, Any]],
    ) -> MigrationRuleBatch:
        """Deterministic extraction from keyword patterns — library-agnostic."""
        rules: list[MigrationRuleDTO] = []
        refs: list[str] = []
        chunks: list[tuple[str, str, Optional[str]]] = []

        for d in docs:
            text = d.get("content") or ""
            if text:
                chunks.append((text, d.get("source_type") or "docs", d.get("url")))
            if d.get("url"):
                refs.append(d["url"])
        for r in releases:
            text = r.get("body") or ""
            if text:
                chunks.append((text, "github_release", r.get("url")))
            if r.get("url"):
                refs.append(r["url"])

        keywords_removed = ("removed", "deleted", "no longer supported", "dropping support")
        keywords_deprecated = ("deprecated", "will be removed", "scheduled for removal")
        keywords_renamed = ("renamed", "replaced by", "use instead", "moved to")
        keywords_security = ("security", "cve-", "vulnerability", "advisory")
        keywords_breaking = ("breaking change", "breaking changes", "incompatible", "backwards incompatible")

        seen_symbols: set[str] = set()
        for text, source_type, url in chunks:
            lower = text.lower()
            # Pull backtick/`code` symbols and dotted identifiers near risk keywords
            import re

            candidates = set(re.findall(r"`([A-Za-z_][\w\.]{2,80})`", text))
            candidates |= set(re.findall(r"\b([a-z_][\w]*\.[A-Za-z_][\w\.]{1,60})\b", text))

            for sym in list(candidates)[:40]:
                if sym in seen_symbols:
                    continue
                idx = lower.find(sym.lower())
                window = lower[max(0, idx - 120) : idx + 120] if idx >= 0 else lower[:400]
                kind = None
                severity = "medium"
                if any(k in window for k in keywords_removed) or any(k in window for k in keywords_breaking):
                    kind = "removed" if any(k in window for k in keywords_removed) else "behavior_change"
                    severity = "high"
                elif any(k in window for k in keywords_deprecated):
                    kind = "deprecated"
                    severity = "medium"
                elif any(k in window for k in keywords_renamed):
                    kind = "renamed"
                    severity = "medium"
                elif any(k in window for k in keywords_security):
                    kind = "security"
                    severity = "high"
                else:
                    continue

                seen_symbols.add(sym)
                rules.append(
                    MigrationRuleDTO(
                        library=library,
                        from_version=from_version,
                        to_version=to_version,
                        symbol=sym,
                        kind=kind,
                        description=f"{kind.replace('_', ' ').title()} signal for `{sym}` found in {source_type}.",
                        severity=severity,
                        confidence=0.45,
                        before=None,
                        after=None,
                        reason="Extracted from documentation/release notes via keyword grounding.",
                        official_reference=url,
                        auto_fixable=False,
                        estimated_effort="medium",
                        source_type=source_type,
                        source_url=url,
                        validation_status="needs_review",
                    )
                )

        summary = (
            f"Extracted {len(rules)} grounded migration signals for {library} "
            f"{from_version}→{to_version} from documentation and release notes."
        )
        return MigrationRuleBatch(rules=rules, summary=summary, official_references=list(dict.fromkeys(refs)))
