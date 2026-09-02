"""Overclaim check for ARC-0019 architecture-review claims.

Every REFUTED row must name DESIGN vs SENTENCE. Probe 2 drops defect_locus
on a REFUTED row and asserts this checker then fails.

Live disagreement is three separate integers plus their sum as a count of
problems. A combined 'agree' score is forbidden. Unreachable modes must
not be marked mitigated.
"""
from __future__ import annotations

from typing import Any

LOCUS = frozenset({"DESIGN", "SENTENCE"})
VERDICTS = frozenset({"REFUTED", "CONFIRMED", "PARTIAL", "NOT-CHECKED"})
REACH = frozenset({"REACHABLE", "UNREACHABLE"})


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
            if not str(row.get("scoped_restatement") or "").strip():
                return False, f"claims[{i}]-REFUTED-missing-scoped_restatement"
            loci.add(locus)
        elif verdict == "CONFIRMED":
            confirmed += 1
    if refuted < 1:
        return False, "no-REFUTED-claim"
    if confirmed < 1:
        return False, "no-CONFIRMED-claim"
    if "DESIGN" not in loci or "SENTENCE" not in loci:
        return False, f"REFUTED-loci-incomplete:{sorted(loci)}"

    live = doc.get("live_reconciliation") or {}
    try:
        a = int(live["registry_not_deployed_count"])
        b = int(live["deployed_not_in_registry_count"])
        h = int(live["hash_mismatch_count"])
        d = int(live["disagreement_count"])
    except (KeyError, TypeError, ValueError):
        return False, "live-counts-not-separate"
    if d != a + b + h:
        return False, "disagreement-count-not-sum"
    for forbidden in (
        "combined_agree_count",
        "combined_consistent_count",
        "agreement_score",
    ):
        if forbidden in live:
            return False, f"{forbidden}-forbidden"
    if a < 0 or b < 0 or h < 0:
        return False, "negative-count"

    split = doc.get("reachability") or {}
    modes = split.get("modes") if isinstance(split, dict) else None
    if not isinstance(modes, list) or len(modes) < 5:
        return False, "reachability-modes-short"
    unreachable = 0
    for j, mode in enumerate(modes):
        if not isinstance(mode, dict):
            return False, f"reachability[{j}]-not-object"
        status = str(mode.get("pr_only_status") or "")
        if status not in REACH:
            return False, f"reachability[{j}]-bad-status"
        if status == "UNREACHABLE":
            unreachable += 1
            if not str(mode.get("reachable_again_if") or "").strip():
                return False, f"reachability[{j}]-missing-reachable_again_if"
            if mode.get("counted_as_mitigated") is not False:
                return False, f"reachability[{j}]-must-set-counted_as_mitigated-false"
            cite = str(mode.get("pr_only_citation") or "")
            if "PR-ONLY" not in cite:
                return False, f"reachability[{j}]-missing-PR-ONLY-citation"
    if unreachable < 1:
        return False, "no-UNREACHABLE-mode"
    return True, f"refuted={refuted} confirmed={confirmed} A={a} B={b} H={h} d={d}"
