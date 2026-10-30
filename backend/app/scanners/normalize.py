"""Normalize Python package names per PEP 503."""

import re
from pathlib import Path


def read_text_auto(path: Path | str) -> str:
    """
    Read a text file with encoding detection.
    Handles UTF-8, UTF-8 BOM, UTF-16 LE/BE (common on Windows-created requirements.txt).
    """
    raw = Path(path).read_bytes()
    if not raw:
        return ""

    # BOM-based detection
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")

    # UTF-16 without BOM: many null bytes in even/odd positions
    if len(raw) >= 4:
        nulls = raw.count(b"\x00")
        if nulls > len(raw) // 4:
            for enc in ("utf-16-le", "utf-16-be", "utf-16"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue

    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            text = raw.decode(enc)
            # Strip leftover NULs if a mis-decode slipped through
            if "\x00" in text:
                text = text.replace("\x00", "")
            return text
        except UnicodeDecodeError:
            continue

    return raw.decode("utf-8", errors="replace").replace("\x00", "")


def normalize_package_name(name: str) -> str:
    """PEP 503 normalized name: lowercase, runs of [-_.] → single hyphen."""
    return re.sub(r"[-_.]+", "-", name.strip()).lower()


def parse_requirement_line(line: str) -> dict | None:
    """
    Parse a single requirements-style line into package metadata.
    Returns None for comments, blanks, flags, and editable/VCS refs we skip.
    """
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return None
    if raw.startswith("-"):
        # Skip -r, -e, --hash, etc. for now (still note included files separately)
        return None

    # Strip inline comments
    if " #" in raw:
        raw = raw.split(" #", 1)[0].strip()

    # Environment markers
    marker = None
    if ";" in raw:
        raw, marker = raw.split(";", 1)
        raw = raw.strip()
        marker = marker.strip()

    # Extras: package[extra1,extra2]
    extras: list[str] = []
    extras_match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\[([^\]]+)\](.*)$", raw)
    if extras_match:
        name = extras_match.group(1)
        extras = [e.strip() for e in extras_match.group(2).split(",") if e.strip()]
        rest = extras_match.group(3).strip()
    else:
        name_match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(.*)$", raw)
        if not name_match:
            return None
        name = name_match.group(1)
        rest = name_match.group(2).strip()

    # Version constraint — support ==, >=, <=, ~=, !=, >, <, and comma-separated
    constraint = rest if rest else None
    version = None
    if constraint:
        eq = re.match(r"^==\s*([^\s,;]+)", constraint)
        if eq:
            version = eq.group(1).strip()

    return {
        "package_name": name,
        "normalized_name": normalize_package_name(name),
        "version": version,
        "constraint": constraint,
        "extras": extras,
        "marker": marker,
        "is_dev": False,
        "is_direct": True,
    }
