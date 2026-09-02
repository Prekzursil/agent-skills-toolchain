"""Overclaim check: every REFUTED claim names DESIGN vs SENTENCE.

A correctly scoped claim is CONFIRMED. Probe 2 mutates a REFUTED row
to drop defect_locus and asserts this checker then fails.

Catalog tests_required for ARC-0030: both DESIGN and SENTENCE loci,
and a correctly scoped restatement on each REFUTED row.
"""
from __future__ import annotations

from typing import Any

LOCUS = frozenset({"DESIGN", "SENTENCE"})
VERDICTS = frozenset({"REFUTED", "CONFIRMED", "PARTIAL", "NOT-CHECKED"})


def _locus(row: dict[str, Any]) -> str:
    return str(row.get("defect_locus") or row.get("defect_locus") or "")


def _restatement(row: dict[str, Any]) -> str:
    return str(
        row.get("scoped_restatement") or row.get("scoped_restatement") or ""
    ).strip()


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
            locus = _locus(row)
            if locus not in LOCUS:
                return False, f"claims[{i}]-REFUTED-missing-defect_locus"
            if not str(row.get("claim") or "").strip():
                return False, f"claims[{i}]-empty-claim"
            if not _restatement(row):
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
    return True, f"refuted={refuted} confirmed={confirmed}"
