"""Author classifier: required-input refusal, then first match in tie-break order."""
from __future__ import annotations

from typing import Any

from vocabulary import RULES, missing_required


def decide(record: dict) -> dict[str, Any]:
    miss = missing_required(record)
    if miss:
        return {
            "id": record.get("id"),
            "disposition": "UNKNOWN-NEEDS-PROBE",
            "reason": "required-input-refusal",
            "missing_input": miss,
            "fired": ["UNKNOWN-NEEDS-PROBE"],
            "method": "first-match-tie-break",
        }
    ordered = sorted(RULES, key=lambda r: int(r["rank"]))
    fired = [r["value"] for r in ordered if r["match"](record)]
    if not fired:
        return {
            "id": record.get("id"),
            "disposition": None,
            "reason": "no-rule-fired",
            "missing_input": None,
            "fired": [],
            "method": "first-match-tie-break",
        }
    winner = fired[0]
    return {
        "id": record.get("id"),
        "disposition": winner,
        "reason": "first-match-tie-break",
        "missing_input": None,
        "fired": fired,
        "method": "first-match-tie-break",
    }
