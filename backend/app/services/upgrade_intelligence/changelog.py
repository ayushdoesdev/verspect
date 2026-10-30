"""Generalized changelog / release-note extraction.

Not a per-package catalog. Extracts identifiers and change kinds from
untrusted documentation text, then later matching happens against repository usage.
"""

from __future__ import annotations

import re
from typing import Any

_HEADING = re.compile(r"^\s{0,3}#{1,4}\s+(.+)$", re.M)
_BULLET = re.compile(r"^\s*[-*+]\s+(.+)$", re.M)
_CODE_SPAN = re.compile(r"`([^`]+)`")
_IDENT = re.compile(
    r"\b([A-Za-z_][\w.]{1,80}|[A-Z][A-Za-z0-9_]+|[a-z][\w]*(?:/[\w.-]+)+)\b"
)

_KIND_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("removed", re.compile(r"\b(removed|deleted|dropped|no longer (?:supported|available)|eliminated)\b", re.I)),
    ("renamed", re.compile(r"\b(renamed|moved to|replaced by|now called)\b", re.I)),
    ("signature_change", re.compile(r"\b(signature|parameters? changed|argument(?:s)? (?:changed|removed)|arity)\b", re.I)),
    ("type_change", re.compile(r"\b(type(?:s)? changed|interface changed|struct field|generic(?:s)?)\b", re.I)),
    ("import_path_change", re.compile(r"\b(import path|module path|package path|renamed package)\b", re.I)),
    ("configuration", re.compile(r"\b(config(?:uration)?|settings?|env(?:ironment)? var|yaml|toml|ini)\b", re.I)),
    ("behavior_change", re.compile(r"\b(default(?:s)? changed|behavior(?:al)? change|now (?:returns|raises|throws)|breaking change)\b", re.I)),
    ("deprecated", re.compile(r"\b(deprecat(?:ed|ion|es)|will be removed)\b", re.I)),
    ("security", re.compile(r"\b(security|cve-\d+|vulnerab|advisory|auth(?:n|z)?)\b", re.I)),
    ("breaking", re.compile(r"\b(breaking(?:\s+change)?|incompatible|migration required)\b", re.I)),
]

_STOP = {
    "the",
    "and",
    "for",
    "this",
    "that",
    "with",
    "from",
    "into",
    "when",
    "added",
    "fixed",
    "update",
    "updated",
    "change",
    "changes",
    "please",
    "note",
    "http",
    "https",
    "www",
    "com",
    "org",
    "see",
    "new",
    "now",
    "also",
    "using",
    "use",
    "api",
    "version",
    "github",
    "refactor",
    "logic",
    "pull",
}


def extract_documented_changes(texts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return structured change mentions grounded in provided excerpts only."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for blob in texts:
        text = (blob.get("text") or blob.get("body") or "")[:12000]
        source = blob.get("url") or blob.get("source") or blob.get("tag") or "release_notes"
        if not text.strip():
            continue
        for line in _candidate_lines(text):
            kinds = [name for name, pat in _KIND_PATTERNS if pat.search(line)]
            if not kinds:
                continue
            identifiers = _identifiers(line)
            if not identifiers:
                continue
            primary = kinds[0]
            for ident in identifiers[:8]:
                key = (primary, ident.lower())
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    {
                        "kind": primary,
                        "identifier": ident,
                        "line": line[:400],
                        "source": str(source),
                        "all_kinds": kinds,
                    }
                )
    return out[:200]


def _candidate_lines(text: str) -> list[str]:
    lines: list[str] = []
    for match in _HEADING.finditer(text):
        lines.append(match.group(1).strip())
    for match in _BULLET.finditer(text):
        lines.append(match.group(1).strip())
    # Also scan short paragraphs that mention change keywords.
    for raw in text.splitlines():
        stripped = raw.strip()
        if 12 <= len(stripped) <= 400 and any(pat.search(stripped) for _, pat in _KIND_PATTERNS):
            lines.append(stripped)
    # Deduplicate preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for line in lines:
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(line)
    return uniq[:400]


def _identifiers(line: str) -> list[str]:
    found: list[str] = []
    for span in _CODE_SPAN.findall(line):
        token = span.strip().strip("()[]{}.,;:")
        if token and token.lower() not in _STOP and len(token) > 1:
            found.append(token)
    for match in _IDENT.finditer(line):
        token = match.group(1)
        if token.lower() in _STOP or len(token) < 3:
            continue
        if token.isnumeric():
            continue
        found.append(token)
    # Dedup
    seen: set[str] = set()
    out: list[str] = []
    for token in found:
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(token)
    return out
