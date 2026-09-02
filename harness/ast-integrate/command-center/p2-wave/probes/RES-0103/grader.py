"""E1-E4 grader. A headline without its baseline is E3 and cannot promote."""
from __future__ import annotations


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, str) and value.strip().upper() in {
        "NONE",
        "N/A",
        "NULL",
    }:
        return False
    return True


def grade_mechanism(mech: dict) -> str:
    if not _present(mech.get("paper_id")):
        return "E3"
    if not _present(mech.get("locator")):
        return "E3"
    if not _present(mech.get("effect_size")):
        return "E3"
    if not _present(mech.get("baseline")):
        return "E3"
    declared = str(mech.get("evidence_tier") or "").upper()
    if declared in {"E1", "E2", "E3", "E4"}:
        return declared
    return "E3"


def can_promote(mech: dict) -> bool:
    return grade_mechanism(mech) in {"E1", "E2"}


grade_mechanism = grade_mechanism
can_promote = can_promote
