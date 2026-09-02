"""Independent classifier: collect every firing rule, then min(rank).

Does not walk the ordered list and stop. Does not read gold labels.
Agreement with decide.py therefore measures the written criteria plus the
total order, not one model's labelling habits.
"""
from __future__ import annotations

from typing import Any

from vocabulary import RULES, missing_required


def decide_independent(record: dict) -> dict[str, Any]:
    miss = missing_required(record)
    if miss:
        return {
            "id": record.get("id"),
            "disposition": "UNKNOWN-NEEDS-PROBE",
            "reason": "required-input-refusal",
            "missing_input": miss,
            "fired": ["UNKNOWN-NEEDS-PROBE"],
            "method": "argmin-rank-over-firing-set",
        }
    hits = [r for r in RULES if r["match"](record)]
    if not hits:
        return {
            "id": record.get("id"),
            "disposition": None,
            "reason": "no-rule-fired",
            "missing_input": None,
            "fired": [],
            "method": "argmin-rank-over-firing-set",
        }
    winner = min(hits, key=lambda r: (int(r["rank"]), r["value"]))
    fired = [r["value"] for r in sorted(hits, key=lambda r: int(r["rank"]))]
    return {
        "id": record.get("id"),
        "disposition": winner["value"],
        "reason": "argmin-rank-over-firing-set",
        "missing_input": None,
        "fired": fired,
        "method": "argmin-rank-over-firing-set",
    }
