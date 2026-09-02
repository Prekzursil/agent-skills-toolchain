"""Overclaim check for ARC-0012 architecture-review claims.

Every REFUTED row must name DESIGN vs SENTENCE. A correctly scoped claim
is CONFIRMED. Probe 2 drops defect_locus on a REFUTED row and asserts
this checker then fails.
"""
from __future__ import annotations

from typing import Any

LOCUS = frozenset({"DESIGN", "SENTENCE"})
VERDICTS = frozenset({"REFUTED", "CONFIRMED", "PARTIAL", "NOT-CHECKED"})


def check_overclaim(doc: dict[str, Any]) -> tuple[bool, str]:
    claims = doc.get("claims")
    if not isinstance(claims, list) or len(claims) < 3:
        return False, "claims-missing-or-short"
    refuted = 0
    confirmed = 0
    for i, row in enumerate(claims):
        if not isinstance(row, dict):
            return False, f"claims[{i}]-not-object"
        verdict = str(row.get("verdict") or "")
        if verdict not in VERDICTS:
            return False, f"claims[{i}]-bad-verdict:{verdict}"
        if verdict == "REFUTED":
            refuted += 1
            locus = str(row.get("defect_locus") or "")
            if locus not in LOCUS:
                return False, f"claims[{i}]-REFUTED-missing-defect_locus"
            if not str(row.get("claim") or "").strip():
                return False, f"claims[{i}]-empty-claim"
        elif verdict == "CONFIRMED":
            confirmed += 1
    if refuted < 1:
        return False, "no-REFUTED-claim"
    if confirmed < 1:
        return False, "no-CONFIRMED-claim"
    # Two counts must exist as separate integers (catalog evidence_requirement)
    live = doc.get("live_completeness") or {}
    try:
        a = int(live["direction_a_orphan_registry_count"])
        b = int(live["direction_b_orphan_output_count"])
    except (KeyError, TypeError, ValueError):
        return False, "live-counts-not-separate"
    if "combined_consistent_count" in live:
        return False, "combined-count-forbidden"
    if a < 0 or b < 0:
        return False, "negative-count"
    return True, f"refuted={refuted} confirmed={confirmed} A={a} B={b}"
