"""Overclaim check for ARC-0061 architecture-review claims.

Every REFUTED row must name DESIGN vs SENTENCE. A correctly scoped claim
is CONFIRMED. Probe 2 drops defect_locus on a REFUTED row and asserts
this checker then fails.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

LOCUS = frozenset({"DESIGN", "SENTENCE"})
VERDICTS = frozenset({"REFUTED", "CONFIRMED", "PARTIAL", "NOT-CHECKED"})

A9_DESIGN = "command-center/phase3/A9/DESIGN.json"


def check_overclaim(doc: dict[str, Any], repo: Path | None = None) -> tuple[bool, str]:
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

    live = doc.get("detector_control") or {}
    try:
        clean_n = int(live["clean_duplicate_count"])
        planted_n = int(live["planted_duplicate_count"])
    except (KeyError, TypeError, ValueError):
        return False, "detector-control-counts-missing"
    if "combined_finding_count" in live:
        return False, "combined-count-forbidden"
    if clean_n < 0 or planted_n < 0:
        return False, "negative-count"
    if planted_n < 1:
        return False, "planted-did-not-fire"
    if live.get("extraction_control_clean") is not True:
        return False, "extraction-control-clean-missing"
    if live.get("a9_design_present") is True:
        if repo is None:
            repo = Path(__file__).resolve().parents[3]
        if not (repo / A9_DESIGN).is_file():
            return False, "overclaim-A9-DESIGN-present"

    rev = doc.get("reviewer") or {}
    if rev.get("enumeration_certified_against_47") is True:
        return False, "overclaim-47-certified"
    return True, (
        f"refuted={refuted} confirmed={confirmed} clean={clean_n} planted={planted_n}"
    )
