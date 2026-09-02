"""Overclaim check for ARC-0023.

Every REFUTED claim names DESIGN vs SENTENCE. A correctly scoped claim
is CONFIRMED. Probe 2 mutates a REFUTED row to drop defect_locus and
asserts this checker then fails.

Also require both loci among REFUTED rows, a live computed observable
list, and an honest falsifiability verdict (not a softened stand-in for
REFUTED-AS-UNFALSIFIABLE).
"""
from __future__ import annotations

from typing import Any

LOCUS = frozenset({"DESIGN", "SENTENCE"})
VERDICTS = frozenset({"REFUTED", "CONFIRMED", "PARTIAL", "NOT-CHECKED"})
FALSIFIABILITY = frozenset(
    {"FALSIFIABLE-WITHOUT-PUBLISH", "REFUTED-AS-UNFALSIFIABLE"}
)
SOFTENED = frozenset(
    {
        "PARTIALLY-UNFALSIFIABLE",
        "MOSTLY-UNFALSIFIABLE",
        "UNCLEAR",
        "UNOBSERVABLE-IN-PRACTICE",
        "THEORETICALLY-FALSIFIABLE",
    }
)


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

    fv = str(doc.get("falsifiability_verdict") or "")
    if fv in SOFTENED:
        return False, f"falsifiability-softened:{fv}"
    if fv not in FALSIFIABILITY:
        return False, f"falsifiability-missing:{fv}"

    obs = doc.get("observables") or {}
    if not isinstance(obs, dict) or obs.get("computed_not_asserted") is not True:
        return False, "observables-not-computed"
    try:
        n = int(obs["count"])
    except (KeyError, TypeError, ValueError):
        return False, "observables-count-missing"
    names = obs.get("ids")
    if not isinstance(names, list):
        return False, "observables-ids-missing"
    if n != len(names):
        return False, "observables-count-mismatch"
    if fv == "FALSIFIABLE-WITHOUT-PUBLISH" and n < 1:
        return False, "falsifiable-but-zero-observables"
    if fv == "REFUTED-AS-UNFALSIFIABLE" and n != 0:
        return False, "unfalsifiable-verdict-but-observables-named"

    headline = str(doc.get("headline_verdict") or "")
    if fv == "FALSIFIABLE-WITHOUT-PUBLISH" and headline == "REFUTED-AS-UNFALSIFIABLE":
        return False, "headline-unfalsifiable-despite-observables"
    if fv == "REFUTED-AS-UNFALSIFIABLE" and headline != "REFUTED-AS-UNFALSIFIABLE":
        return False, "unfalsifiable-not-recorded-as-headline"

    quote = str(doc.get("pr_only_quote") or "")
    if "never a public marketplace release" not in quote:
        return False, "pr-only-quote-missing"
    cond = doc.get("stopping_condition_13") or {}
    if not isinstance(cond, dict):
        return False, "condition-13-missing"
    if str(cond.get("verdict") or "") != "UNSATISFIABLE-AS-WRITTEN":
        return False, "condition-13-not-unsatisfiable-as-written"
    return True, f"refuted={refuted} confirmed={confirmed} observables={n}"
