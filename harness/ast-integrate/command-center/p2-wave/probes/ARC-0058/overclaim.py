"""Overclaim check for ARC-0058.

Every REFUTED claim names DESIGN vs SENTENCE. A correctly scoped claim is
CONFIRMED. The unit must distinguish refuting UX-first as the ORGANIZING
principle from refuting individual polish items. Evidence-or-cut: no
UNPROVEN class. Ranking must be computed.
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
    saw_principle = False
    saw_items_survive = False
    for i, row in enumerate(claims):
        if not isinstance(row, dict):
            return False, f"claims[{i}]-not-object"
        verdict = str(row.get("verdict") or "")
        if verdict not in VERDICTS:
            return False, f"claims[{i}]-bad-verdict:{verdict}"
        claim = str(row.get("claim") or "").strip()
        if not claim:
            return False, f"claims[{i}]-empty-claim"
        scope = str(row.get("scope") or "")
        if scope == "ORGANIZING-PRINCIPLE":
            saw_principle = True
        if scope == "INDIVIDUAL-ITEM":
            saw_items_survive = True
        if verdict == "REFUTED":
            refuted += 1
            locus = str(row.get("defect_locus") or "")
            if locus not in LOCUS:
                return False, f"claims[{i}]-REFUTED-missing-defect_locus"
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
    if not saw_principle or not saw_items_survive:
        return False, "scope-statement-missing-principle-vs-item"
    scope_obj = doc.get("scope")
    if not isinstance(scope_obj, dict):
        return False, "scope-object-missing"
    if str(scope_obj.get("organizing_principle_verdict") or "") != "REFUTED":
        return False, "organizing-principle-not-REFUTED"
    if scope_obj.get("individual_items_not_blanket_refuted") is not True:
        return False, "items-blanket-refuted"
    cut = doc.get("evidence_or_cut")
    if not isinstance(cut, dict) or cut.get("unproven_rejected") is not True:
        return False, "evidence-or-cut-unproven-not-rejected"
    if "UNPROVEN" in str(cut.get("classes") or ""):
        return False, "UNPROVEN-class-present"
    ranked = doc.get("ranking")
    if not isinstance(ranked, dict) or ranked.get("computed_not_asserted") is not True:
        return False, "ranking-not-computed"
    order = ranked.get("order")
    if not isinstance(order, list) or len(order) < 1:
        return False, "ranking-order-empty"
    return True, f"refuted={refuted} confirmed={confirmed}"
