"""Overclaim check for ARC-0062 SECURITY.json.

REFUTED rows must name DESIGN vs SENTENCE and restate the surviving scope.
Both loci must appear. Reconciliation and the bypass plant must be computed.
"""
from __future__ import annotations

from typing import Any

from hybrid import SINGLE_EVALUATOR_NODE

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

    rec = doc.get("reconciliation") or {}
    if not isinstance(rec, dict) or rec.get("computed") is not True:
        return False, "reconciliation-not-computed"
    if rec.get("empty_minuend") is not True:
        return False, "reconciliation-gap:" + ",".join(
            str(x) for x in (rec.get("missing") or [])
        )

    plant = doc.get("bypass_proof") or {}
    if not isinstance(plant, dict) or plant.get("plant_caught") is not True:
        return False, "bypass-plant-not-caught"
    if plant.get("clean_finding_count") != 0:
        return False, "clean-hybrid-not-zero-findings"

    paths = doc.get("entry_paths") or []
    if not isinstance(paths, list) or len(paths) < 8:
        return False, "entry-paths-short"
    for i, row in enumerate(paths):
        if not isinstance(row, dict):
            return False, f"entry_paths[{i}]-not-object"
        hops = row.get("hops") or []
        if SINGLE_EVALUATOR_NODE not in hops:
            return False, f"entry_paths[{i}]-missing-evaluator:{row.get('id')}"
    return True, f"refuted={refuted} confirmed={confirmed} paths={len(paths)}"
