"""Licence verification stage for scout prior-art (IMP-0210)."""
from __future__ import annotations

from typing import Any

from vocabulary import ADOPT_FAMILY, DISPOSITION_VOCABULARY, assert_disposition


def _spdx(candidate: dict[str, Any]) -> str:
    raw = candidate.get("licence") or candidate.get("license")
    if not isinstance(raw, str) or not raw.strip():
        return "UNKNOWN"
    token = raw.strip()
    if token.upper() in {"MIT", "MIT-0"}:
        return "MIT"
    if token.upper().startswith("GPL"):
        return "GPL-3.0-only"
    if token.upper() in {"APACHE-2.0", "APACHE-2"}:
        return "Apache-2.0"
    if token.lower() in {"permissive", "oss", "open"}:
        return "UNKNOWN"
    return token


def verify_one(candidate: dict[str, Any], target_spdx: str = "") -> dict[str, Any]:
    cid = str(candidate.get("id") or "")
    spdx = _spdx(candidate)
    riders = candidate.get("licence_riders") or candidate.get("license_riders") or []
    if spdx == "UNKNOWN":
        disp = "CLEAN-ROOM-REIMPLEMENT"
        reason = "LICENCE-UNKNOWN"
        recommended = False
    elif riders:
        disp = "CLEAN-ROOM-REIMPLEMENT"
        reason = "LICENCE-RIDER"
        recommended = False
    elif spdx.startswith("GPL"):
        disp = "CLEAN-ROOM-REIMPLEMENT"
        reason = "LICENCE-COPYLEFT"
        recommended = False
    else:
        disp = "ADOPT-AS-IS"
        reason = "LICENCE-PERMISSIVE"
        recommended = True
    assert_disposition(disp)
    return {
        "id": cid,
        "disposition": disp,
        "reason": reason,
        "spdx": spdx,
        "recommended": recommended,
        "adopt_family": disp in ADOPT_FAMILY,
        "target_spdx": target_spdx,
    }


def verify_candidates(batch: list[dict[str, Any]], target_spdx: str = "") -> dict[str, Any]:
    hits = [verify_one(c, target_spdx=target_spdx) for c in batch]
    return {"hits": hits, "n": len(hits)}
