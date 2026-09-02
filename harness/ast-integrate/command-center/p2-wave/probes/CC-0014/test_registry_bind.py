"""Bind tests to claims to units. UNPROVEN is not coverage."""
from __future__ import annotations

from typing import Any


class RegistryContractError(ValueError):
    pass


def classify(row: dict[str, Any]) -> str:
    mutation = row.get("mutation") if isinstance(row.get("mutation"), dict) else None
    forced = str(row.get("status") or "")
    if forced == "PROTECTING" and not (
        mutation and mutation.get("outcome") == "KILLED" and mutation.get("diff") and mutation.get("failing_output")
    ):
        raise RegistryContractError("PROTECTING requires a KILLED mutation with diff and failing_output")
    if mutation:
        outcome = str(mutation.get("outcome") or "")
        if outcome == "KILLED" and mutation.get("diff") and mutation.get("failing_output"):
            return "PROTECTING"
        if outcome == "SURVIVED":
            return "HOLE"
    return "UNPROVEN"


def bind_row(
    test_id: str,
    claim_id: str,
    unit_id: str,
    mutation: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "test_id": test_id,
        "claim_id": claim_id,
        "unit_id": unit_id,
    }
    if mutation is not None:
        row["mutation"] = mutation
    if extra:
        for k, v in extra.items():
            if k != "status":
                row[k] = v
    row["status"] = classify(row)
    return row


def coverage_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    protecting = 0
    holes = 0
    unproven = 0
    for e in entries:
        status = e.get("status") or classify(e)
        if status == "PROTECTING":
            protecting += 1
        elif status == "HOLE":
            holes += 1
        else:
            unproven += 1
    total = len(entries)
    percent = (protecting / total * 100.0) if total else 0.0
    return {
        "claims_total": total,
        "protected_claims": protecting,
        "protected_percent": percent,
        "holes": holes,
        "unproven": unproven,
        "unproven_counted_as_coverage": False,
        "all_unproven_reports_zero_not_hundred": protecting == 0,
    }
