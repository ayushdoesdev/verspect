"""Structured per-category AI fill with untrusted fencing and validation."""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from app.ai.exceptions import classify_ai_failure
from app.ai.prompts import PromptTemplates
from app.core.logging import get_logger
from app.services.upgrade_intelligence.categories import CATEGORY_TITLES, CategoryId
from app.services.upgrade_intelligence.merge import apply_ai_category
from app.services.upgrade_intelligence.models import (
    AffectedLocation,
    CategoryFinding,
    ClaimStatus,
    EvidenceBundle,
    EvidenceItem,
    IntelligenceReport,
)

logger = get_logger(__name__)

_VALID_STATUS: set[str] = {"verified", "likely", "possible", "unresolved"}
_CATEGORY_LIST_KEYS = (
    "categories",
    "incomplete_categories",
    "categories_to_fill",
    "results",
    "data",
)


def coerce_ai_fill_payload(raw: Any) -> dict[str, Any]:
    """Accept structured fills even when the model echoes the request key name."""
    if isinstance(raw, list):
        raw = {"categories": raw}
    if not isinstance(raw, dict):
        return {}

    notes = raw.get("notes")
    rows: list[Any] | None = None
    for key in _CATEGORY_LIST_KEYS:
        value = raw.get(key)
        if isinstance(value, list):
            rows = value
            break
        if key == "categories" and isinstance(value, dict):
            rows = [
                {**item, "category": item.get("category") or cid}
                for cid, item in value.items()
                if isinstance(item, dict)
            ]
            break

    if rows is None:
        return raw if "categories" in raw else {}

    repaired: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = row.get("category") or row.get("id")
        if not cid:
            continue
        item = dict(row)
        item["category"] = cid
        repaired.append(item)
    out: dict[str, Any] = {"categories": repaired}
    if notes:
        out["notes"] = notes
    return out


class AIFindingPayload(BaseModel):
    category: str
    finding: str
    explanation: str = ""
    affected_files: list[dict[str, Any]] = Field(default_factory=list)
    affected_lines: list[int] = Field(default_factory=list)
    required_change: Optional[str] = None
    confidence: float = 0.4
    evidence: list[str] = Field(default_factory=list)
    source: Optional[str] = None
    status: str = "possible"


class AICategoryPayload(BaseModel):
    category: str
    answer: str = ""
    status: str = "possible"
    findings: list[AIFindingPayload] = Field(default_factory=list)


class AIFillResponse(BaseModel):
    categories: list[AICategoryPayload] = Field(default_factory=list)
    notes: Optional[str] = None


class CategoryAIFiller:
    """Fill incomplete analysis categories. Never called when the plan lacks AI."""

    def __init__(self, ai: Any) -> None:
        self.ai = ai

    @property
    def available(self) -> bool:
        return bool(getattr(self.ai, "available", False))

    def fill(
        self,
        report: IntelligenceReport,
        *,
        incomplete: list[CategoryId],
        evidence: EvidenceBundle,
        usages: list[dict[str, Any]],
        repository_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
    ) -> tuple[IntelligenceReport, Optional[str]]:
        if not incomplete:
            return report, None
        if not self.available:
            report.degradation.append("ai_unavailable")
            report.ai_skipped_reason = "ai_unavailable"
            for cid in incomplete:
                cat = report.category(cid)
                cat.ai_skipped_reason = "ai_unavailable"
            return report, "AI completion is currently unavailable."

        usage_files = {
            str(u.get("file_path") or "")
            for u in usages
            if u.get("file_path")
        }
        usage_apis = {
            str(u.get("fully_qualified_name") or u.get("symbol") or "").lower()
            for u in usages
            if u.get("fully_qualified_name") or u.get("symbol")
        }

        payload = self._build_payload(report, incomplete, evidence, usages)
        user = PromptTemplates.upgrade_category_user(payload)
        logger.info(
            "upgrade_category_ai_request",
            incomplete_categories=len(incomplete),
            prompt_chars=len(user),
            payload_chars=len(json.dumps(payload, default=str)),
        )
        report.timings = {**(report.timings or {}), "prompt_chars": len(user)}
        try:
            raw = self.ai._respond_json(
                PromptTemplates.upgrade_category_system(),
                user,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("upgrade_category_ai_failed", error=str(exc)[:400])
            flag = classify_ai_failure(exc)
            if flag not in report.degradation:
                report.degradation.append(flag)
            report.ai_skipped_reason = flag
            for cid in incomplete:
                cat = report.category(cid)
                cat.ai_skipped_reason = flag
            user_msg = {
                "ai_timeout": "AI-assisted analysis timed out.",
                "ai_unavailable": "AI completion is currently unavailable.",
                "ai_rate_limited": "AI provider rate-limited the request.",
                "malformed_ai_response": "AI returned a malformed response.",
            }.get(flag, "AI completion failed.")
            return report, user_msg

        raw = coerce_ai_fill_payload(raw)
        if not raw or "categories" not in raw:
            keys = list(raw.keys())[:12] if isinstance(raw, dict) else [type(raw).__name__]
            logger.warning("upgrade_category_ai_malformed", keys=keys)
            report.degradation.append("malformed_ai_response")
            report.ai_skipped_reason = "malformed_ai_response"
            for cid in incomplete:
                report.category(cid).ai_skipped_reason = "malformed_ai_response"
            return report, "AI returned a malformed response."

        try:
            parsed = AIFillResponse.model_validate(raw)
        except ValidationError:
            categories = raw.get("categories") if isinstance(raw.get("categories"), list) else []
            repaired = []
            for row in categories:
                if isinstance(row, dict) and row.get("category"):
                    repaired.append(row)
            try:
                parsed = AIFillResponse.model_validate({"categories": repaired})
            except ValidationError:
                report.degradation.append("malformed_ai_response")
                report.ai_skipped_reason = "malformed_ai_response"
                for cid in incomplete:
                    report.category(cid).ai_skipped_reason = "malformed_ai_response"
                return report, "AI returned a malformed response."

        by_id = {row.category: row for row in parsed.categories if row.category}
        for cid in incomplete:
            row = by_id.get(cid)
            cat = report.category(cid)
            if row is None:
                cat.ai_invoked = True
                continue
            findings = [
                self._validate_finding(item, usage_files, usage_apis, evidence)
                for item in row.findings
            ]
            findings = [f for f in findings if f is not None]
            status = row.status if row.status in _VALID_STATUS else "possible"
            apply_ai_category(
                cat,
                findings,
                row.answer,
                claim_status=status,  # type: ignore[arg-type]
            )
        report.ai_invoked = True
        extra = dict(report.timings or {})
        extra["ai_response_chars"] = len(json.dumps(raw, default=str))
        extra["ai_categories_returned"] = len(parsed.categories)
        extra["prompt_chars"] = len(user)
        report.timings = extra
        logger.info(
            "upgrade_category_ai_response",
            categories=len(parsed.categories),
            response_chars=extra["ai_response_chars"],
            prompt_chars=extra["prompt_chars"],
        )
        return report, None

    def _build_payload(
        self,
        report: IntelligenceReport,
        incomplete: list[CategoryId],
        evidence: EvidenceBundle,
        usages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        usage_excerpt = []
        for u in usages[:80]:
            usage_excerpt.append(
                {
                    "file": u.get("file_path"),
                    "line": u.get("line"),
                    "api": u.get("fully_qualified_name") or u.get("symbol"),
                    "kind": u.get("usage_kind"),
                    "snippet": (u.get("code_snippet") or "")[:180],
                }
            )
        det = {}
        for cid in incomplete:
            cat = report.category(cid)
            det[cid] = {
                "title": CATEGORY_TITLES.get(cid, cid),
                "completeness": cat.deterministic_completeness,
                "answer": cat.answer,
                "gaps": cat.gaps,
                "findings": [
                    {
                        "finding": f.finding,
                        "explanation": f.explanation,
                        "status": f.status,
                        "files": [loc.file for loc in f.affected_files],
                    }
                    for f in cat.findings[:12]
                ],
            }
        notes = []
        for n in (evidence.release_notes or [])[:8]:
            notes.append(
                {
                    "source": n.get("source"),
                    "version": n.get("version"),
                    "text": (n.get("text") or "")[:2500],
                }
            )
        return {
            "package_name": report.package_name,
            "ecosystem": report.ecosystem,
            "current_version": report.from_version,
            "target_version": report.to_version,
            "categories_to_fill": [
                {"id": cid, "title": CATEGORY_TITLES.get(cid, cid)} for cid in incomplete
            ],
            "deterministic_findings": det,
            "documented_changes": evidence.extracted_changes[:40],
            "release_notes": notes,
            "repository_usage": usage_excerpt,
            "output_schema": {
                "categories": [
                    {
                        "category": "category_id",
                        "answer": "string",
                        "status": "verified|likely|possible|unresolved",
                        "findings": [
                            {
                                "category": "category_id",
                                "finding": "string",
                                "explanation": "string",
                                "affected_files": [
                                    {"file": "path", "line": 0, "api": "symbol", "reason": "string"}
                                ],
                                "affected_lines": [0],
                                "required_change": "repository-specific instruction or null",
                                "confidence": 0.0,
                                "evidence": ["quote from provided notes"],
                                "source": "url or source name",
                                "status": "verified|likely|possible|unresolved",
                            }
                        ],
                    }
                ]
            },
        }

    def _validate_finding(
        self,
        item: AIFindingPayload,
        usage_files: set[str],
        usage_apis: set[str],
        evidence: EvidenceBundle,
    ) -> Optional[CategoryFinding]:
        finding = (item.finding or "").strip()
        if not finding:
            return None
        status = item.status if item.status in _VALID_STATUS else "possible"
        # AI cannot self-certify verified without overlapping usage or extracted identifiers.
        extracted_ids = {
            str(c.get("identifier") or "").lower() for c in evidence.extracted_changes
        }
        leaf = finding.split(".")[-1].lower()
        grounded = leaf in extracted_ids or any(leaf and leaf in api for api in usage_apis)
        if status == "verified" and not grounded:
            status = "likely" if (item.evidence or item.source) else "possible"

        locations: list[AffectedLocation] = []
        for raw in item.affected_files[:20]:
            if not isinstance(raw, dict):
                continue
            path = str(raw.get("file") or raw.get("file_path") or "").strip()
            if not path:
                continue
            in_usage = path in usage_files
            if not in_usage:
                # Vague similarity must never become a definite affected-file claim.
                continue
            locations.append(
                AffectedLocation(
                    file=path,
                    line=raw.get("line"),
                    api=raw.get("api") or finding,
                    reason=str(raw.get("reason") or item.explanation or "")[:400],
                    confidence=min(float(item.confidence or 0.4), 0.75),
                    analysis_method="ai",
                    usage_kind="verified",
                    snippet=raw.get("snippet"),
                )
            )

        evidence_items = [
            EvidenceItem(
                kind="ai_citation",
                text=str(e)[:500],
                source=item.source,
                reliability="low",
                untrusted=True,
            )
            for e in (item.evidence or [])[:6]
        ]
        conf = float(item.confidence or 0.4)
        if conf > 1:
            conf = conf / 100.0
        conf = max(0.0, min(0.75, conf))  # cap AI-only confidence
        allowed_lines = [loc.line for loc in locations if loc.line is not None]
        return CategoryFinding(
            category=item.category,
            finding=finding[:300],
            explanation=(item.explanation or "")[:800],
            affected_files=locations,
            affected_lines=allowed_lines[:20],
            required_change=item.required_change,
            confidence=conf,
            evidence=evidence_items,
            source=item.source,
            analysis_method="ai",
            status=status,  # type: ignore[arg-type]
        )
