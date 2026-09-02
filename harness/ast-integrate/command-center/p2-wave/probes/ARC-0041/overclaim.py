"""Overclaim check for ARC-0041 architecture review."""
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
    if str(doc.get("state") or "") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return False, "self-declared-not-delivering"
    if "SUCCESS:ARC-0041" not in str(doc.get("sentinel") or ""):
        return False, "sentinel-missing"
    corpus = doc.get("injection_corpus") or {}
    if corpus.get("computed_not_asserted") is not True:
        return False, "corpus-not-computed"
    if corpus.get("p1_zero_catch_classes"):
        return False, "zero-catch-class"
    nf = doc.get("never_forward") or {}
    if nf.get("fail_closed_clean") is not True:
        return False, "never-forward-not-clean"
    if nf.get("fail_open_mutant_leaks_canary") is not True:
        return False, "fail-open-detector-silent"
    if nf.get("signals_agree_closed") is not True:
        return False, "never-forward-signals-disagree"
    return True, f"refuted={refuted} confirmed={confirmed}"
