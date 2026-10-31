"""Overclaim check for ARC-0048 architecture-review claims.

Every REFUTED row must name DESIGN vs SENTENCE. Probe 2 drops defect_locus
on a REFUTED row and asserts this checker then fails. Classification
discipline: STRUCTURALLY IMPOSSIBLE rows must name a mechanism.
"""
from __future__ import annotations

from typing import Any

LOCUS = frozenset({"DESIGN", "SENTENCE"})
VERDICTS = frozenset({"REFUTED", "CONFIRMED", "PARTIAL", "NOT-CHECKED"})
SI = "STRUCTURALLY IMPOSSIBLE"
PF = "MERELY POLICY-FORBIDDEN"


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

    paths = doc.get("escalation_paths")
    if not isinstance(paths, list) or len(paths) < 8:
        return False, "escalation-paths-short"
    si = 0
    pf = 0
    surfaces: set[str] = set()
    for i, row in enumerate(paths):
        if not isinstance(row, dict):
            return False, f"paths[{i}]-not-object"
        surfaces.add(str(row.get("surface") or ""))
        cls = str(row.get("classification") or "")
        if cls == SI:
            si += 1
            if len(str(row.get("mechanism") or "").strip()) < 16:
                return False, f"paths[{i}]-SI-missing-mechanism"
            if row.get("marker_reached_tool_call") is True:
                return False, f"paths[{i}]-SI-reached"
        elif cls == PF:
            pf += 1
        else:
            return False, f"paths[{i}]-bad-class:{cls}"
    need = {"skill", "workflow", "council", "marketplace"}
    if not need.issubset(surfaces):
        return False, f"surfaces-incomplete:{sorted(surfaces)}"
    if si < 1 or pf < 1:
        return False, f"class-mix si={si} pf={pf}"

    markers = doc.get("marker_payload") or {}
    if markers.get("intact_any_reached") is True:
        return False, "intact-marker-reached"
    if markers.get("mutant_any_reached") is not True:
        return False, "mutant-did-not-reach"
    if markers.get("mention_silent") is not True:
        return False, "mention-not-silent"
    if doc.get("adv_rebuild_circle") is True:
        return False, "adv-rebuild-circle"
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return False, f"self-declared:{doc.get('state')}"
    return True, f"refuted={refuted} confirmed={confirmed} si={si} pf={pf}"
