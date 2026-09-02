"""Artifact invariants for CNF-0119.

1. Never adjudicate by counting agents.
2. Overclaim is REFUTED (confirmer wins) even when code_was_fine, with a scoped rewrite.
3. Original wording is retained; deleting it is forbidden.
"""
from __future__ import annotations

from typing import Any

SENTINEL = (
    "SUCCESS:CNF-0119 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every case has a decisive "
    "probe output and, where the fault was wording, a correctly scoped "
    "replacement sentence. Any other terminal state is FAILED:CNF-0119 "
    "<classification> with the diagnostic tail attached."
)


def check_artifact(doc: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "not-object"
    if doc.get("unit_id") != "CNF-0119":
        return False, f"unit_id:{doc.get('unit_id')}"
    if doc.get("adjudication_method") != "decisive-probe":
        return False, "adjudication_method-not-decisive-probe"
    if SENTINEL not in str(doc.get("sentinel") or "") and SENTINEL not in str(doc):
        return False, "sentinel-absent"
    cases = doc.get("cases")
    if not isinstance(cases, list) or len(cases) < 8:
        return False, f"cases-short:{0 if not isinstance(cases, list) else len(cases)}"
    overclaim = 0
    real_defect = 0
    wording_rewrites = 0
    majority_overridden = 0
    for i, row in enumerate(cases):
        if not isinstance(row, dict):
            return False, f"cases[{i}]-not-object"
        original = str(row.get("original_wording") or "").strip()
        if len(original) < 8:
            return False, f"cases[{i}]-original_wording-missing"
        probe = row.get("decisive_probe")
        if not isinstance(probe, dict):
            return False, f"cases[{i}]-decisive_probe-missing"
        if len(str(probe.get("output") or "")) < 8:
            return False, f"cases[{i}]-probe-output-empty"
        if probe.get("supports") not in {"implementer", "confirmer", "neither"}:
            return False, f"cases[{i}]-probe-supports-missing"
        if row.get("winning_side") != probe.get("supports"):
            return False, f"cases[{i}]-winning_side-is-not-probe"
        votes = row.get("agent_votes") or {}
        maj = row.get("majority_would_have_picked")
        if maj in {"implementer", "confirmer"} and maj != row.get("winning_side"):
            if row.get("majority_overridden") is not True:
                return False, f"cases[{i}]-majority-overridden-not-flagged"
            majority_overridden += 1
        cls = row.get("classification")
        if cls == "overclaim":
            overclaim += 1
            scoped = str(row.get("correctly_scoped_statement") or "").strip()
            if len(scoped) < 8:
                return False, f"cases[{i}]-overclaim-missing-scoped-sentence"
            if scoped == original:
                return False, f"cases[{i}]-scoped-equals-original"
            if row.get("code_was_fine") is not True:
                return False, f"cases[{i}]-overclaim-code-not-fine"
            if row.get("winning_side") != "confirmer":
                return False, f"cases[{i}]-overclaim-must-refute-wording"
            wording_rewrites += 1
        elif cls == "real-defect":
            real_defect += 1
            if row.get("code_was_fine") is True:
                return False, f"cases[{i}]-real-defect-but-code-fine"
        elif cls == "irreducible-disagreement":
            pass
        else:
            return False, f"cases[{i}]-bad-classification:{cls}"
        if row.get("adjudication_method") not in (None, "decisive-probe"):
            return False, f"cases[{i}]-voted"
    if overclaim < 1:
        return False, "no-overclaim-case"
    if real_defect < 1:
        return False, "no-real-defect-case"
    if wording_rewrites != overclaim:
        return False, "wording-rewrite-mismatch"
    if majority_overridden < 1:
        return False, "no-majority-overridden-control"
    return (
        True,
        f"cases={len(cases)} overclaim={overclaim} real-defect={real_defect} "
        f"majority_overridden={majority_overridden}",
    )


def wording_deleted_fails(doc: dict[str, Any]) -> bool:
    """Control: deleting original_wording must make check_artifact fail."""
    import copy

    mutant = copy.deepcopy(doc)
    cases = mutant.get("cases") or []
    if not cases:
        return False
    cases[0]["original_wording"] = ""
    ok, _ = check_artifact(mutant)
    return not ok


def majority_vote_fails(doc: dict[str, Any]) -> bool:
    """Control: taking the vote instead of the probe must fail the checker."""
    import copy

    mutant = copy.deepcopy(doc)
    for row in mutant.get("cases") or []:
        if row.get("majority_overridden"):
            row["winning_side"] = row.get("majority_would_have_picked")
            break
    else:
        return False
    ok, _ = check_artifact(mutant)
    return not ok
