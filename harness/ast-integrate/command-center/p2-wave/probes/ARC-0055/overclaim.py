"""Overclaim check for ARC-0055.

Every REFUTED claim names DESIGN vs SENTENCE and a scoped restatement.
Both loci must appear. Blast-radius classification must be computed.
Fatigue must carry before and after rates from real sessions.
"""
from __future__ import annotations

from typing import Any

LOCUS = frozenset({"DESIGN", "SENTENCE"})
VERDICTS = frozenset({"REFUTED", "CONFIRMED", "PARTIAL", "NOT-CHECKED"})
STANCES = frozenset({"DEFAULTED", "EXPLICIT"})


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

    br = doc.get("blast_radius") or {}
    if not isinstance(br, dict) or br.get("computed_not_asserted") is not True:
        return False, "blast-radius-not-computed"
    try:
        n_files = int(br["marketplace_files_written_on_one_click"])
        n_write = int(br["catalog_write_without_owner_gate"])
    except (KeyError, TypeError, ValueError):
        return False, "blast-radius-counts-missing"
    if n_files < 1 or n_write < 1:
        return False, "blast-radius-counts-nonpositive"

    decisions = doc.get("decisions") or []
    if not isinstance(decisions, list) or len(decisions) < 3:
        return False, "decisions-missing-or-short"
    stances = set()
    for i, d in enumerate(decisions):
        if not isinstance(d, dict):
            return False, f"decisions[{i}]-not-object"
        stance = str(d.get("stance") or "")
        if stance not in STANCES:
            return False, f"decisions[{i}]-bad-stance"
        stances.add(stance)
        if not str(d.get("reversal_cost") or "").strip():
            return False, f"decisions[{i}]-missing-reversal_cost"
        if not str(d.get("worst_case_if_default_wrong") or "").strip():
            return False, f"decisions[{i}]-missing-worst-case"
        radius = d.get("blast_radius") or {}
        if not isinstance(radius, dict) or radius.get("computed_not_asserted") is not True:
            return False, f"decisions[{i}]-blast-not-computed"
        if "value" not in radius:
            return False, f"decisions[{i}]-blast-value-missing"
    if "DEFAULTED" not in stances or "EXPLICIT" not in stances:
        return False, f"stances-incomplete:{sorted(stances)}"

    fat = doc.get("fatigue") or {}
    if not isinstance(fat, dict) or fat.get("computed_not_asserted") is not True:
        return False, "fatigue-not-computed"
    if int(fat.get("session_count") or 0) < 1:
        return False, "fatigue-no-real-session"
    if "before_actual_pph_wall" not in fat or "after_proposed_pph_wall" not in fat:
        return False, "fatigue-before-after-missing"
    if fat.get("both_signals_kept") is not True:
        return False, "fatigue-dropped-a-signal"
    if (doc.get("a8_design") or {}).get("present") is True:
        return False, "a8-design-claimed-present"
    return True, f"refuted={refuted} confirmed={confirmed} files={n_files} write_no_oa={n_write}"
