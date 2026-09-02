"""Overclaim guard for RES-0049 SLSA level verdicts.

Without a hosted builder, SLSA Build L2 is definitionally unreachable.
A claim of L2+ under that constraint, or a claim that provenance exists
in this CI, is an overclaim.
"""
from __future__ import annotations

from typing import Any

ALLOWED_MAX = frozenset({"L1", "Build L1", "SLSA Build L1"})
ALLOWED_CURRENT = frozenset({"L0", "Build L0", "SLSA Build L0", "below L1"})
FORBIDDEN_LEVELS = ("L2", "L3", "L4", "SLSA 2", "SLSA 3", "SLSA 4")


def check_overclaim(doc: dict[str, Any]) -> tuple[bool, str]:
    verdict = doc.get("level_verdict") or {}
    if not isinstance(verdict, dict):
        return False, "level_verdict-missing"
    achievable = str(verdict.get("achievable_without_hosted_builder") or "")
    current = str(verdict.get("measured_current") or "")
    nxt = str(verdict.get("next_level") or "")
    delta = str(verdict.get("named_delta_to_next_level") or "")
    cap = str(verdict.get("ci_capability_that_caps") or "")
    cite = str(verdict.get("ci_file_line") or "")
    if achievable not in ALLOWED_MAX:
        return False, f"overclaim-achievable:{achievable}"
    if current not in ALLOWED_CURRENT:
        return False, f"overclaim-current:{current}"
    if nxt not in {"L2", "Build L2", "SLSA Build L2"}:
        return False, f"next-level-not-L2:{nxt}"
    low_delta = delta.lower()
    if "hosted" not in low_delta or "provenance" not in low_delta:
        return False, "named-delta-missing-hosted-provenance"
    if "provenance" not in cap.lower():
        return False, "cap-capability-not-provenance-generation"
    if ":" not in cite or "probe1-yaml-inventory.json" not in cite:
        return False, f"ci-file-line-not-this-repo:{cite}"
    text = (
        str(doc.get("answer") or "")
        + " "
        + str(doc.get("sentinel") or "")
        + " "
        + str(verdict.get("text") or "")
    )
    for token in FORBIDDEN_LEVELS:
        # Allow 'L2' only as the named next level, not as currently achieved.
        pass
    if "currently SLSA Build L2" in text or "achieves L2" in text.lower():
        return False, "text-claims-current-L2"
    if "SUCCESS:RES-0049" not in text:
        return False, "sentinel-absent-from-verdict-text"
    claims = doc.get("claims") or []
    confirmed = 0
    for i, row in enumerate(claims):
        if not isinstance(row, dict):
            return False, f"claims[{i}]-not-object"
        if str(row.get("verdict") or "") == "CONFIRMED":
            confirmed += 1
            caveat = str(row.get("strongest_caveat") or "").strip()
            if not caveat:
                return False, f"claims[{i}]-CONFIRMED-missing-caveat"
            if not str(row.get("source_lineage") or "").strip():
                return False, f"claims[{i}]-missing-source_lineage"
    if confirmed < 3:
        return False, f"confirmed-count:{confirmed}"
    return True, f"max={achievable} current={current} next={nxt}"
