"""Persist optional feedback screenshots to local disk."""

from __future__ import annotations

import base64
import binascii
import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, status

# Keep uploads under the app data directory (mounted/persistent in compose when configured).
UPLOAD_ROOT = Path("/app/data/feedback_screenshots")
MAX_BYTES = 2 * 1024 * 1024  # 2 MB
ALLOWED_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

_DATA_URL_RE = re.compile(
    r"^data:(image/(?:png|jpeg|jpg|webp|gif));base64,(.+)$",
    re.IGNORECASE | re.DOTALL,
)


def save_feedback_screenshot(
    *,
    feedback_id: UUID,
    screenshot_data_url: str,
) -> str:
    """
    Decode a data-URL screenshot and write it to disk.

    Returns a relative path string stored on the feedback row.
    """
    match = _DATA_URL_RE.match((screenshot_data_url or "").strip())
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Screenshot must be a PNG, JPEG, WebP, or GIF data URL.",
        )
    content_type = match.group(1).lower()
    if content_type == "image/jpg":
        content_type = "image/jpeg"
    ext = ALLOWED_TYPES.get(content_type)
    if not ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported screenshot type.",
        )
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Screenshot data is invalid.",
        ) from exc
    if len(raw) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Screenshot must be 2 MB or smaller.",
        )

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    filename = f"{feedback_id}_{uuid4().hex[:8]}{ext}"
    path = UPLOAD_ROOT / filename
    path.write_bytes(raw)
    return str(path)
