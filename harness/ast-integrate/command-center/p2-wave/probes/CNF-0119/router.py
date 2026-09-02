"""Local discrepancy router: a record cannot close without a disposition.

CNF-0013's artifact is absent. This module is the router this unit actually
runs: null disposition is refused; accepted-residual needs a named settling
experiment; a fully dispositioned record closes.
"""
from __future__ import annotations

DISPOSITIONS = frozenset(
    {
        "implementation-defect",
        "confirmation-defect",
        "specification-ambiguity",
        "environment-difference",
        "accepted-residual",
        "overclaim",
        "real-defect",
        "irreducible-disagreement",
    }
)


def close(record: dict) -> tuple[bool, str]:
    disp = record.get("disposition")
    if disp is None or disp == "":
        return False, "null-disposition-refused"
    if disp not in DISPOSITIONS:
        return False, f"unknown-disposition:{disp}"
    if disp == "accepted-residual" and not str(record.get("settling_experiment") or "").strip():
        return False, "accepted-residual-missing-settling-experiment"
    if not str(record.get("id") or "").strip():
        return False, "missing-id"
    return True, "closed"


def classify_to_disposition(classification: str) -> str:
    if classification == "overclaim":
        return "overclaim"
    if classification == "real-defect":
        return "implementation-defect"
    if classification == "irreducible-disagreement":
        return "irreducible-disagreement"
    return classification
