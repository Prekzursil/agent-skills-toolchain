"""Overclaim check: every REFUTED claim names DESIGN vs SENTENCE.

A correctly scoped claim is CONFIRMED. Probe 2 mutates a REFUTED row
to drop defect_locus and asserts this checker then fails.
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
    loci: set[str] = set()
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
            loci.add(locus)
        elif verdict == "CONFIRMED":
            confirmed += 1
    if refuted < 1:
        return False, "no-REFUTED-claim"
    if confirmed < 1:
        return False, "no-CONFIRMED-claim"
    if "DESIGN" not in loci or "SENTENCE" not in loci:
        return False, f"REFUTED-loci-incomplete:{sorted(loci)}"
    both = doc.get("both_directions") or {}
    keep = both.get("non_negotiable_regardless_of_friction") or []
    drop = both.get("dropped_because_permission_theater") or []
    if not isinstance(keep, list) or len(keep) < 3:
        return False, "both-directions-keep-short"
    if not isinstance(drop, list) or len(drop) < 2:
        return False, "both-directions-drop-short"
    surviving = doc.get("minimal_surviving_control_set") or []
    if not isinstance(surviving, list) or len(surviving) < 3:
        return False, "minimal-surviving-set-short"
    return True, f"refuted={refuted} confirmed={confirmed}"


check_overclaim = check_overclaim
