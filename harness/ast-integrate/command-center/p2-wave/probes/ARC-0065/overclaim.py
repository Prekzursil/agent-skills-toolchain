"""Overclaim check: REFUTED rows name DESIGN vs SENTENCE; hybrid test is falsifiable.

A correctly scoped claim is CONFIRMED. Probe 2 drops defect_locus on a
REFUTED row and asserts this checker then fails.
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

    pair = doc.get("named_pair") or {}
    subs = pair.get("subsystems") if isinstance(pair, dict) else None
    if not isinstance(subs, list) or len(subs) != 2:
        return False, "named-pair-missing"
    if not all(isinstance(s, dict) and str(s.get("id") or "").strip() for s in subs):
        return False, "named-pair-ids-missing"
    if str(pair.get("capability") or "") != "skills":
        return False, "named-pair-not-skills"
    cited = pair.get("adjacent_rows")
    if not isinstance(cited, list) or len(cited) != 2:
        return False, "adjacent-rows-missing"

    table = doc.get("capability_to_authority") or []
    if not isinstance(table, list) or len(table) < 4:
        return False, "authority-table-short"
    for i, row in enumerate(table):
        if not isinstance(row, dict):
            return False, f"table[{i}]-not-object"
        if not str(row.get("capability") or "") or not str(row.get("authority") or ""):
            return False, f"table[{i}]-incomplete"
        auths = row.get("authorities")
        if auths is not None:
            return False, f"table[{i}]-multi-authority-cell"

    ft = doc.get("falsifiable_test") or {}
    if not isinstance(ft, dict):
        return False, "falsifiable-test-missing"
    if not str(ft.get("hybrid_worse_if") or "").strip():
        return False, "hybrid-worse-if-missing"
    if not str(ft.get("hybrid_confirmed_if") or "").strip():
        return False, "hybrid-confirmed-if-missing"
    if "correctness first" not in str(ft.get("objective_function") or ""):
        return False, "objective-function-not-catalog"
    if ft.get("preference_not_measurement") is True:
        return False, "test-is-preference"
    if ft.get("computed_not_asserted") is not True:
        return False, "comparison-not-computed"

    scope = doc.get("scope") or {}
    if not isinstance(scope, dict):
        return False, "scope-missing"
    if scope.get("refutes_composition_in_general") is not False:
        return False, "scope-overclaim-general-composition"
    if scope.get("refutes_this_composition") is not True:
        return False, "scope-this-composition-missing"

    if doc.get("a9_design_present") is True:
        return False, "a9-design-overclaim"
    if doc.get("adv_rebuild_circle") is True:
        return False, "adv-rebuild-circle"

    det = doc.get("singularity_detector") or {}
    if not isinstance(det, dict) or det.get("computed_not_asserted") is not True:
        return False, "detector-not-computed"
    try:
        n_dup = int(det["duplicate_class_count"])
        n_single = int(det["best_single_duplicate_class_count"])
    except (KeyError, TypeError, ValueError):
        return False, "detector-counts-missing"
    if n_dup < 1:
        return False, "maximal-not-shown-duplicate"
    if n_single != 0:
        return False, "best-single-not-singular"

    return True, f"refuted={refuted} confirmed={confirmed} dup={n_dup}"
