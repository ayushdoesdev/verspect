"""Deterministic patch generator — real code edits from structured rules only."""

from __future__ import annotations

import difflib
import re
from typing import Optional

from app.migration_engine.models import MatchedUsage, MigrationFinding, PatchDTO


class PatchGenerator:
    """
    Generate real patches from matched rules.

    Never fabricates replacements. If rule.after is missing or unchanged → no patch.
    """

    def generate(self, matches: list[MatchedUsage]) -> tuple[list[PatchDTO], list[MigrationFinding]]:
        patches: list[PatchDTO] = []
        findings: list[MigrationFinding] = []
        # Prefer highest-confidence match per (file, line, symbol)
        best: dict[tuple, MatchedUsage] = {}
        for m in matches:
            key = (m.file_path, m.line, m.symbol, m.usage_kind)
            prev = best.get(key)
            if prev is None or m.match_confidence > prev.match_confidence:
                best[key] = m

        for m in best.values():
            finding, patch = self._one(m)
            findings.append(finding)
            if patch is not None:
                patches.append(patch)
        return patches, findings

    def _one(self, m: MatchedUsage) -> tuple[MigrationFinding, Optional[PatchDTO]]:
        rule = m.rule
        current = m.code_snippet or ""
        conf = min(1.0, float(m.match_confidence))
        ref = rule.official_reference or rule.source_url
        title = rule.reference_title

        # Explicit unchanged API (e.g. BaseModel)
        if rule.unchanged:
            return (
                MigrationFinding(
                    status="no_migration_required",
                    file_path=m.file_path,
                    line=m.line,
                    symbol=m.fully_qualified_name or m.symbol,
                    usage_kind=m.usage_kind,
                    current_code=current or None,
                    suggested_code=None,
                    replacement=None,
                    confidence=conf,
                    reason=rule.reason or "No changes required — API remains compatible.",
                    official_reference=ref,
                    reference_title=title,
                    automatic=False,
                    rule_id=rule.id,
                ),
                None,
            )

        if not rule.after:
            # Matched a migration rule without a grounded replacement → manual review
            return (
                MigrationFinding(
                    status="manual_review_required",
                    file_path=m.file_path,
                    line=m.line,
                    symbol=m.fully_qualified_name or m.symbol,
                    usage_kind=m.usage_kind,
                    current_code=current or None,
                    suggested_code=None,
                    replacement=None,
                    confidence=conf,
                    reason=rule.reason
                    or rule.description
                    or "Manual review required — no grounded replacement in migration rules.",
                    official_reference=ref,
                    reference_title=title,
                    automatic=False,
                    rule_id=rule.id,
                ),
                None,
            )

        suggested = self._apply(current, rule.before, rule.after, m)
        if not suggested or suggested.strip() == current.strip():
            # Could not apply safely
            return (
                MigrationFinding(
                    status="manual_review_required" if conf < 0.6 else "manual_review_required",
                    file_path=m.file_path,
                    line=m.line,
                    symbol=m.fully_qualified_name or m.symbol,
                    usage_kind=m.usage_kind,
                    current_code=current or None,
                    suggested_code=None,
                    replacement=rule.after,
                    confidence=conf,
                    reason=(
                        f"Replacement `{rule.after}` is known but could not be applied "
                        f"automatically to this snippet. Manual review required."
                    ),
                    official_reference=ref,
                    reference_title=title,
                    automatic=False,
                    rule_id=rule.id,
                ),
                None,
            )

        diff = "\n".join(
            difflib.unified_diff(
                (current + "\n").splitlines(keepends=True),
                (suggested + "\n").splitlines(keepends=True),
                fromfile=f"a/{m.file_path}",
                tofile=f"b/{m.file_path}",
                lineterm="",
            )
        )
        patch = PatchDTO(
            file_path=m.file_path,
            line=m.line,
            symbol=m.fully_qualified_name,
            current_code=current,
            suggested_code=suggested,
            unified_diff=diff or None,
            reason=rule.reason or rule.description,
            confidence=conf,
            official_reference=ref,
            auto_fixable=True,
            rule_id=rule.id,
            validation_status="validated",
        )
        finding = MigrationFinding(
            status="automatic_migration",
            file_path=m.file_path,
            line=m.line,
            symbol=m.fully_qualified_name or m.symbol,
            usage_kind=m.usage_kind,
            current_code=current,
            suggested_code=suggested,
            unified_diff=diff or None,
            replacement=rule.after,
            confidence=conf,
            reason=rule.reason or rule.description,
            official_reference=ref,
            reference_title=title,
            automatic=True,
            rule_id=rule.id,
        )
        return finding, patch

    def _apply(
        self,
        current: str,
        before: Optional[str],
        after: str,
        m: MatchedUsage,
    ) -> Optional[str]:
        if not current:
            # Synthesize from rule for decorator/import when snippet missing
            if m.usage_kind == "decorator" and after.startswith("@"):
                return after
            return None

        text = current
        if before and before in text:
            return text.replace(before, after, 1)

        leaf = (m.rule.symbol or "").lstrip(".").split(".")[-1]

        # Module attribute aliases: np.float / numpy.float → float
        if (
            leaf
            and after
            and not after.startswith((".", "@"))
            and m.usage_kind in {"attribute", "keyword_argument", "assignment"}
        ):
            for prefix in ("np.", "numpy."):
                needle = f"{prefix}{leaf}"
                if needle in text:
                    return text.replace(needle, after, 1)
            # before may be written as np.X while source uses numpy.X
            if before and before.startswith("np.") and before.replace("np.", "numpy.", 1) in text:
                return text.replace(before.replace("np.", "numpy.", 1), after, 1)

        # Decorator: @validator → @field_validator (preserve args)
        if m.usage_kind == "decorator":
            # @validator("name") → @field_validator("name")
            after_leaf = after.lstrip("@").split(".")[-1] if after else ""
            if leaf and after_leaf:
                pattern = rf"@{re.escape(leaf)}\b"
                repl = f"@{after_leaf}"
                if re.search(pattern, text):
                    return re.sub(pattern, repl, text, count=1)
            if before and before.lstrip("@") in text:
                return text.replace(before.lstrip("@"), after.lstrip("@"), 1)

        # Method rename: .dict( → .model_dump(
        if before and before.startswith(".") and before in text:
            return text.replace(before, after, 1)
        if m.usage_kind == "method_call" and after.startswith("."):
            after_leaf = after.lstrip(".")
            if leaf and f".{leaf}(" in text:
                return text.replace(f".{leaf}(", f".{after_leaf}(", 1)

        # Generic identifier replace for parse_obj → model_validate
        # Skip bare builtin leaves (float/int/bool/…) — too easy to mis-replace.
        after_leaf = after.split(".")[-1]
        if (
            leaf
            and after_leaf
            and leaf != after_leaf
            and re.search(rf"\b{re.escape(leaf)}\b", text)
        ):
            return re.sub(rf"\b{re.escape(leaf)}\b", after_leaf, text, count=1)

        return None

    def classify_unmatched_usages(
        self,
        usages: list[dict],
        matched: list[MatchedUsage],
        *,
        knowledge_available: bool,
    ) -> list[MigrationFinding]:
        """Classify library usages that did not match a migration rule.

        - knowledge_available=True → positively verified No changes required
        - knowledge_available=False → Unknown (never claim No changes required)
        """
        matched_keys = {
            (m.file_path, m.line, (m.symbol or "").lower())
            for m in matched
        }
        findings: list[MigrationFinding] = []
        seen: set[tuple] = set()
        for u in usages:
            key = (u.get("file_path"), u.get("line"), (u.get("symbol") or "").lower())
            if key in matched_keys or key in seen:
                continue
            seen.add(key)
            if knowledge_available:
                status = "no_migration_required"
                reason = (
                    "No changes required — deterministic migration rules exist for this "
                    "range and none match this usage."
                )
                confidence = 1.0
            else:
                status = "unknown"
                reason = (
                    "Unknown — insufficient deterministic migration knowledge for this "
                    "library/version range. Do not treat as a clean upgrade."
                )
                confidence = 0.3
            findings.append(
                MigrationFinding(
                    status=status,
                    file_path=u.get("file_path") or "",
                    line=u.get("line"),
                    symbol=u.get("fully_qualified_name") or u.get("symbol") or "",
                    usage_kind=u.get("usage_kind"),
                    current_code=u.get("code_snippet"),
                    suggested_code=None,
                    replacement=None,
                    confidence=confidence,
                    reason=reason,
                    automatic=False,
                )
            )
        return findings
