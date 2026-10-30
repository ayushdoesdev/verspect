"""License detection and policy enforcement."""

from __future__ import annotations

import re
from typing import Optional

from app.core.config import get_settings
from app.core.enums import LicensePolicyAction
from app.core.logging import get_logger

logger = get_logger(__name__)

# Map common license strings / classifiers to SPDX-like identifiers
LICENSE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bAGPL[- ]?3(\.0)?\b", re.I), "AGPL-3.0"),
    (re.compile(r"\bAGPL[- ]?1(\.0)?\b", re.I), "AGPL-1.0"),
    (re.compile(r"Affero General Public License\s*v?3", re.I), "AGPL-3.0"),
    (re.compile(r"\bLGPL[- ]?3(\.0)?\b", re.I), "LGPL-3.0"),
    (re.compile(r"\bLGPL[- ]?2\.1\b", re.I), "LGPL-2.1"),
    (re.compile(r"\bLGPL[- ]?2(\.0)?\b", re.I), "LGPL-2.0"),
    (re.compile(r"Lesser General Public License\s*v?3", re.I), "LGPL-3.0"),
    (re.compile(r"Lesser General Public License\s*v?2\.1", re.I), "LGPL-2.1"),
    (re.compile(r"(?<![AL])\bGPL[- ]?3(\.0)?\b", re.I), "GPL-3.0"),
    (re.compile(r"(?<![AL])\bGPL[- ]?2(\.0)?\b", re.I), "GPL-2.0"),
    (re.compile(r"GNU General Public License\s*v?3", re.I), "GPL-3.0"),
    (re.compile(r"GNU General Public License\s*v?2", re.I), "GPL-2.0"),
    (re.compile(r"\bApache[- ]?2(\.0)?\b", re.I), "Apache-2.0"),
    (re.compile(r"\bApache\b", re.I), "Apache-2.0"),
    (re.compile(r"\bMIT\b", re.I), "MIT"),
    (re.compile(r"\bBSD[- ]?3", re.I), "BSD-3-Clause"),
    (re.compile(r"\bBSD[- ]?2", re.I), "BSD-2-Clause"),
    (re.compile(r"\bBSD\b", re.I), "BSD-3-Clause"),
    (re.compile(r"\bMPL[- ]?2(\.0)?\b", re.I), "MPL-2.0"),
    (re.compile(r"\bISC\b", re.I), "ISC"),
    (re.compile(r"\bUnlicense\b", re.I), "Unlicense"),
    (re.compile(r"\bProprietary\b", re.I), "Commercial"),
    (re.compile(r"\bCommercial\b", re.I), "Commercial"),
]

CLASSIFIER_MAP = {
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: BSD License": "BSD-3-Clause",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)": "GPL-3.0",
    "License :: OSI Approved :: GNU General Public License v2 (GPLv2)": "GPL-2.0",
    "License :: OSI Approved :: GNU Affero General Public License v3": "AGPL-3.0",
    "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0",
    "License :: OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)": "LGPL-2.0",
    "License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)": "LGPL-2.1",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "License :: OSI Approved :: ISC License (ISCL)": "ISC",
    "License :: Other/Proprietary License": "Commercial",
}


def detect_license(
    license_raw: Optional[str] = None,
    classifier: Optional[str] = None,
) -> Optional[str]:
    if classifier and classifier in CLASSIFIER_MAP:
        return CLASSIFIER_MAP[classifier]
    if classifier:
        for pattern, spdx in LICENSE_PATTERNS:
            if pattern.search(classifier):
                return spdx
    if license_raw:
        # Exact SPDX short
        cleaned = license_raw.strip()
        upper = cleaned.upper()
        known = {
            "MIT", "APACHE-2.0", "BSD-3-CLAUSE", "BSD-2-CLAUSE",
            "GPL-3.0", "GPL-2.0", "AGPL-3.0", "LGPL-3.0", "LGPL-2.1",
            "MPL-2.0", "ISC", "UNLICENSE",
        }
        if upper in known or cleaned in {
            "MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause",
            "GPL-3.0", "GPL-2.0", "AGPL-3.0", "LGPL-3.0", "LGPL-2.1",
        }:
            return cleaned if cleaned[0].isupper() else upper
        for pattern, spdx in LICENSE_PATTERNS:
            if pattern.search(license_raw):
                return spdx
    return None


def evaluate_license_policy(
    spdx: Optional[str],
    reject_list: Optional[list[str]] = None,
    warn_list: Optional[list[str]] = None,
) -> str:
    settings = get_settings()
    # None → global defaults; [] → explicit empty org policy
    reject = settings.license_reject_list if reject_list is None else reject_list
    warn = settings.license_warn_list if warn_list is None else warn_list

    if not spdx:
        return LicensePolicyAction.WARN.value

    normalized = spdx.upper().replace(" ", "")

    def _matches(policy_item: str, candidate: str) -> bool:
        item = policy_item.replace(" ", "").upper()
        # Exact or prefix match on SPDX id (avoid GPL matching inside LGPL/AGPL)
        return candidate == item or candidate.startswith(item + "-") or item == candidate

    for item in reject:
        if _matches(item, normalized):
            return LicensePolicyAction.REJECT.value
    for item in warn:
        if _matches(item, normalized):
            return LicensePolicyAction.WARN.value
    return LicensePolicyAction.ALLOW.value


class LicenseChecker:
    def check(
        self,
        license_raw: Optional[str] = None,
        classifier: Optional[str] = None,
        reject_override: Optional[list[str]] = None,
        warn_override: Optional[list[str]] = None,
    ) -> dict:
        spdx = detect_license(license_raw, classifier)
        action = evaluate_license_policy(spdx, reject_override, warn_override)
        return {
            "license_spdx": spdx,
            "license_raw": license_raw,
            "license_policy_action": action,
        }
