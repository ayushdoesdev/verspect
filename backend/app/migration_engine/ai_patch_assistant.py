"""Team+ AI Migration Assistant — enrichment only.

Produces explanations, reasoning, and suggested replacements as guidance.
Never changes deterministic Upgrade Simulator verdicts (migration_status).
"""

from __future__ import annotations

from typing import Any, Optional

from app.ai.analyzer import AIAnalyzer
from app.ai.prompts import PromptTemplates
from app.core.logging import get_logger
from app.services.upgrade_helpers import build_migration_finding, code_differs

logger = get_logger(__name__)


class AIMigrationPatchAssistant:
    def __init__(self, ai: Optional[AIAnalyzer] = None) -> None:
        from app.ai.analyzer import DisabledAIAnalyzer

        # Never None — locked/missing AI is a handle with available=False.
        self.ai = ai if ai is not None else DisabledAIAnalyzer()

    def generate(
        self,
        *,
        package_name: str,
        from_version: str,
        to_version: str,
        usages: list[dict[str, Any]],
        rules: list[Any],
        official_references: list[str],
        documentation_excerpts: list[dict[str, Any]],
        release_notes: list[dict[str, Any]],
        deterministic_findings: list[dict[str, Any]] | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Return (enrichment_rows, error_message).

        Enrichment rows may include suggested_code / explanation but their
        ``migration_status`` is informational only — merge must ignore it.
        """
        if not self.ai.available:
            return [], "AI provider unavailable"

        rule_dicts: list[dict[str, Any]] = []
        for r in rules:
            if hasattr(r, "model_dump"):
                rule_dicts.append(r.model_dump())
            elif isinstance(r, dict):
                rule_dicts.append(r)

        candidates = _select_candidate_usages(usages, rule_dicts, deterministic_findings)
        if not candidates:
            return [], None

        payload = {
            "package_name": package_name,
            "from_version": from_version,
            "to_version": to_version,
            "usages": candidates[:80],
            "rules": [
                {
                    "symbol": r.get("symbol"),
                    "kind": r.get("kind"),
                    "before": r.get("before"),
                    "after": r.get("after"),
                    "description": r.get("description"),
                    "official_reference": r.get("official_reference") or r.get("source_url"),
                    "unchanged": r.get("unchanged"),
                }
                for r in rule_dicts[:40]
            ],
            "official_references": official_references[:12],
            "documentation": [
                {
                    "title": d.get("title"),
                    "url": d.get("url"),
                    "content": (d.get("content") or "")[:4000],
                }
                for d in documentation_excerpts[:6]
            ],
            "release_notes": [
                {
                    "version": r.get("version") or r.get("tag"),
                    "title": r.get("title") or r.get("name"),
                    "body": (r.get("body") or "")[:4000],
                }
                for r in release_notes[:8]
            ],
        }

        try:
            raw = self.ai.service.complete_json(
                PromptTemplates.migration_assistant_patches_system(),
                PromptTemplates.migration_assistant_patches_user(payload),
                operation="migration_assistant_patches",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ai_migration_assistant_invoke_failed", error=str(exc)[:500])
            return [], str(exc)[:500]

        patches_raw = raw.get("patches") if isinstance(raw, dict) else None
        if not isinstance(patches_raw, list):
            return [], "AI returned no patch list"

        findings: list[dict[str, Any]] = []
        for item in patches_raw[:60]:
            if not isinstance(item, dict):
                continue
            current = item.get("current_code") or item.get("before") or ""
            suggested = item.get("suggested_code") or item.get("after")
            explanation = (
                item.get("explanation")
                or item.get("reasoning")
                or item.get("migration_notes")
                or "AI migration guidance"
            )
            # Build for structure only — merge will strip status into enrichment fields.
            finding = build_migration_finding(
                file_path=str(item.get("file_path") or ""),
                line=item.get("line"),
                symbol=item.get("symbol") or item.get("fully_qualified_name"),
                current_code=current,
                suggested_code=suggested if suggested and code_differs(current, suggested) else None,
                explanation=str(explanation),
                confidence=float(item.get("confidence") or 0.5),
                automatic=False,
                official_reference=item.get("official_reference"),
                validation_status="needs_review",
                risk_flagged=True,
            )
            finding["source"] = "ai_migration_assistant"
            finding["reasoning"] = item.get("reasoning") or item.get("explanation")
            finding["migration_notes"] = item.get("migration_notes")
            finding["ai_suggested_code"] = (
                suggested if suggested and code_differs(current, str(suggested)) else None
            )
            finding["ai_explanation"] = str(explanation)
            finding["ai_confidence"] = float(item.get("confidence") or 0.5)
            findings.append(finding)

        return findings, None


def merge_assistant_with_deterministic(
    deterministic: list[dict[str, Any]],
    ai_patches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Enrich deterministic findings with AI guidance — never change verdicts.

    Preserves ``migration_status``, ``status_title``, ``automatic``, and
    deterministic ``suggested_code`` / patches. AI may only add guidance fields.
    """
    if not ai_patches:
        return deterministic

    def key(row: dict[str, Any]) -> tuple:
        return (
            row.get("file_path") or "",
            row.get("line"),
            (row.get("symbol") or "").split(".")[-1].lower(),
        )

    out: dict[tuple, dict[str, Any]] = {key(d): dict(d) for d in deterministic}
    for patch in ai_patches:
        k = key(patch)
        prev = out.get(k)
        if prev is None:
            # Do not invent new simulator verdicts from AI-only sites.
            continue

        merged = dict(prev)
        # Preserve deterministic verdict fields explicitly.
        det_status = prev.get("migration_status")
        merged["migration_status"] = det_status
        merged["status_title"] = prev.get("status_title")
        merged["automatic"] = prev.get("automatic")
        merged["suggested_code"] = prev.get("suggested_code")
        merged["unified_diff"] = prev.get("unified_diff")
        merged["replacement"] = prev.get("replacement")

        ai_expl = patch.get("ai_explanation") or patch.get("explanation")
        if ai_expl:
            merged["ai_explanation"] = ai_expl
            merged["reasoning"] = patch.get("reasoning") or ai_expl
        if patch.get("migration_notes"):
            merged["migration_notes"] = patch.get("migration_notes")
        ai_code = patch.get("ai_suggested_code") or (
            patch.get("suggested_code")
            if code_differs(patch.get("current_code"), patch.get("suggested_code"))
            else None
        )
        if ai_code:
            merged["ai_suggested_code"] = ai_code
        if patch.get("ai_confidence") is not None:
            merged["ai_confidence"] = patch.get("ai_confidence")
        elif patch.get("confidence") is not None:
            merged["ai_confidence"] = patch.get("confidence")

        merged["source"] = "ai_migration_assistant+deterministic"
        out[k] = merged

    return list(out.values())


def _select_candidate_usages(
    usages: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    deterministic_findings: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    actionable_symbols = {
        (r.get("symbol") or "").split(".")[-1].lower()
        for r in rules
        if r.get("symbol") and not r.get("unchanged")
    }
    selected: list[dict[str, Any]] = []
    for u in usages:
        leaf = (u.get("symbol") or u.get("fully_qualified_name") or "").split(".")[-1].lower()
        fqn = (u.get("fully_qualified_name") or "").lower()
        if leaf in actionable_symbols or any(s and s in fqn for s in actionable_symbols):
            selected.append(
                {
                    "file_path": u.get("file_path"),
                    "line": u.get("line"),
                    "symbol": u.get("symbol"),
                    "fully_qualified_name": u.get("fully_qualified_name"),
                    "usage_kind": u.get("usage_kind"),
                    "code_snippet": u.get("code_snippet"),
                    "enclosing_function": u.get("enclosing_function"),
                    "enclosing_class": u.get("enclosing_class"),
                }
            )
    if selected:
        return selected

    out = []
    for f in deterministic_findings or []:
        if f.get("migration_status") in {
            "automatic_migration",
            "manual_review_required",
            "unknown",
        }:
            out.append(
                {
                    "file_path": f.get("file_path"),
                    "line": f.get("line"),
                    "symbol": f.get("symbol"),
                    "code_snippet": f.get("current_code"),
                    "usage_kind": f.get("usage_kind"),
                }
            )
    if out:
        return out
    return [
        {
            "file_path": u.get("file_path"),
            "line": u.get("line"),
            "symbol": u.get("symbol"),
            "fully_qualified_name": u.get("fully_qualified_name"),
            "usage_kind": u.get("usage_kind"),
            "code_snippet": u.get("code_snippet"),
        }
        for u in usages[:40]
    ]
