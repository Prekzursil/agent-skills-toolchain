"""Overclaim check: REFUTED rows must name DESIGN vs SENTENCE."""
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
        elif verdict == "CONFIRMED":
            confirmed += 1
    if refuted < 1:
        return False, "no-REFUTED-claim"
    if confirmed < 1:
        return False, "no-CONFIRMED-claim"
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return False, f"self-declared:{doc.get('state')}"
    return True, f"refuted={refuted} confirmed={confirmed}"
