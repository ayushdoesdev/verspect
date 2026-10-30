"""Validate migration rules and generated patches (AST / Black / Ruff)."""

from __future__ import annotations

import ast
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.migration_engine.models import MigrationRuleDTO, PatchDTO, ValidationStatus
from app.models.knowledge import MigrationRule, ValidationHistory

logger = get_logger(__name__)


class RuleValidator:
    def __init__(self, session: Optional[Session] = None) -> None:
        self.session = session

    def validate_rule(self, rule: MigrationRuleDTO) -> tuple[str, list[str]]:
        """Schema + grounding checks for a rule. Returns (status, errors)."""
        errors: list[str] = []
        if not rule.symbol or len(rule.symbol) < 2:
            errors.append("symbol too short")
        if not rule.description:
            errors.append("missing description")
        if rule.kind not in {
            "removed",
            "deprecated",
            "renamed",
            "signature_change",
            "behavior_change",
            "import_path_change",
            "security",
            "performance",
            "added",
        }:
            errors.append(f"invalid kind: {rule.kind}")
        if rule.auto_fixable:
            if not rule.after:
                errors.append("auto_fixable requires after snippet grounded in docs")
            if not (rule.official_reference or rule.source_url):
                errors.append("auto_fixable requires official_reference or source_url")
        if rule.before:
            ok, err = self.validate_python_snippet(rule.before)
            if not ok:
                errors.append(f"before snippet AST invalid: {err}")
        if rule.after:
            ok, err = self.validate_python_snippet(rule.after)
            if not ok:
                errors.append(f"after snippet AST invalid: {err}")

        if errors:
            return ValidationStatus.REJECTED.value, errors
        if rule.confidence < 0.4 or not (rule.official_reference or rule.source_url):
            return ValidationStatus.NEEDS_REVIEW.value, []
        return ValidationStatus.VALIDATED.value, []

    def validate_python_snippet(self, code: str) -> tuple[bool, str]:
        """Parse as module or as expression/statement fragment."""
        text = (code or "").strip()
        if not text:
            return False, "empty"
        try:
            ast.parse(text)
            return True, ""
        except SyntaxError:
            pass
        last = "syntax error"
        for wrapped in (
            text,
            f"{text}\n",
            f"def _():\n    {text}\n",
            f"class _:\n    {text}\n",
        ):
            try:
                ast.parse(wrapped)
                return True, ""
            except SyntaxError as exc:
                last = str(exc)
        return False, last

    def validate_patch(self, patch: PatchDTO) -> PatchDTO:
        errors: list[str] = []

        ok, err = self.validate_python_snippet(patch.suggested_code)
        if not ok:
            errors.append(f"AST: {err}")

        # Black check if available
        black_err = self._run_formatter_check(patch.suggested_code, tool="black")
        if black_err:
            errors.append(black_err)

        # Ruff check if available
        ruff_err = self._run_formatter_check(patch.suggested_code, tool="ruff")
        if ruff_err:
            errors.append(ruff_err)

        if errors:
            # AST failure is hard reject; formatter issues → needs_review but keep patch
            hard = any(e.startswith("AST:") for e in errors)
            patch.validation_status = (
                ValidationStatus.REJECTED.value if hard else ValidationStatus.NEEDS_REVIEW.value
            )
            patch.validation_errors = errors
            patch.auto_fixable = False if hard else patch.auto_fixable
        else:
            patch.validation_status = ValidationStatus.VALIDATED.value
            patch.validation_errors = []

        if self.session and patch.rule_id:
            try:
                self.session.add(
                    ValidationHistory(
                        entity_type="patch",
                        entity_id=UUID(patch.rule_id) if patch.rule_id else UUID(int=0),
                        validator="ast+black+ruff",
                        status="failed" if errors else "passed",
                        message="; ".join(errors) if errors else "ok",
                        details={"errors": errors},
                    )
                )
            except Exception:
                pass
        return patch

    def apply_rule_validation_to_db(self, rule_orm: MigrationRule, dto: MigrationRuleDTO) -> None:
        status, errors = self.validate_rule(dto)
        rule_orm.validation_status = status
        if self.session:
            self.session.add(
                ValidationHistory(
                    entity_type="rule",
                    entity_id=rule_orm.id,
                    validator="schema+ast+grounding",
                    status="passed" if status == ValidationStatus.VALIDATED.value else "failed",
                    message="; ".join(errors) if errors else "ok",
                    details={"errors": errors, "status": status},
                )
            )

    def _run_formatter_check(self, code: str, tool: str) -> Optional[str]:
        exe = shutil.which(tool)
        if not exe:
            return None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "snippet.py"
                path.write_text(code + ("\n" if not code.endswith("\n") else ""), encoding="utf-8")
                if tool == "black":
                    proc = subprocess.run(
                        [exe, "--check", "--quiet", str(path)],
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                    if proc.returncode not in (0, 1):
                        return None
                    if proc.returncode == 1:
                        return "black: would reformat"
                elif tool == "ruff":
                    proc = subprocess.run(
                        [exe, "check", "--quiet", str(path)],
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                    if proc.returncode not in (0, 1):
                        return None
                    if proc.returncode == 1:
                        msg = (proc.stdout or proc.stderr or "issues found").strip().splitlines()
                        return f"ruff: {msg[0] if msg else 'issues found'}"
        except Exception as exc:
            logger.debug("formatter_check_skipped", tool=tool, error=str(exc))
        return None
