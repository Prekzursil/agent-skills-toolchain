"""Overclaim check: every REFUTED claim names DESIGN vs SENTENCE.

A correctly scoped claim is CONFIRMED. Probe 2 mutates a REFUTED row
to drop defect_locus and asserts this checker then fails.

Also require both loci among REFUTED rows (catalog tests_required:
DESIGN vs SENTENCE) and a computed blast-radius object.
"""
from __future__ import annotations

from typing import Any

from payload import domain

LOCUS = frozenset({"DESIGN", "SENTENCE"})
VERDICTS = frozenset({"REFUTED", "CONFIRMED", "PARTIAL", "NOT-CHECKED"})


def check_overclaim(doc: dict[str, Any]) -> tuple[bool, str]:
    body = domain(doc)
    claims = body.get("claims")
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
    br = body.get("blast_radius") or {}
    if not isinstance(br, dict) or br.get("computed_not_asserted") is not True:
        return False, "blast-radius-not-computed"
    try:
        n = int(br["generated_file_count"])
        a = int(br["files_affected_by_one_shared_path_bug"])
    except (KeyError, TypeError, ValueError):
        return False, "blast-radius-counts-missing"
    if n < 1 or a < 1:
        return False, "blast-radius-counts-nonpositive"
    hatch = body.get("escape_hatch") or {}
    if not isinstance(hatch, dict) or not str(hatch.get("corpus_capability") or "").strip():
        return False, "escape-hatch-corpus-missing"
    return True, f"refuted={refuted} confirmed={confirmed}"
