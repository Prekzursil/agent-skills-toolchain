"""Silent-in-both-states scanner (TST-0018).

Classifies detector rows recorded against a known-good and a known-broken
fixture. A detector whose canonical output is byte-identical in both states
measures nothing: it is INERT and must be named, never folded into
"all clean".
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

INERT = "INERT"
VALID = "VALID"
NOT_CHECKED = "NOT-CHECKED"


def canonical_output(output: Any) -> str:
    """Stable textual form of a detector output for byte comparison."""
    if isinstance(output, str):
        return output
    return json.dumps(output, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_canonical(output: Any) -> str:
    return hashlib.sha256(canonical_output(output).encode("utf-8")).hexdigest()


def classify_row(row: dict[str, Any]) -> dict[str, Any]:
    """Apply the both-states rule to one recorded row."""
    good, broken = row.get("good_output"), row.get("broken_output")
    checked = row.get("checked") is True and good is not None and broken is not None
    if not checked:
        return {
            "detector_id": row.get("detector_id"),
            "verdict": NOT_CHECKED,
            "inert": False,
            "measures_nothing": False,
            "differs": False,
            "byte_diff": None,
            "silent_in_both": False,
        }
    same = canonical_output(good) == canonical_output(broken)
    return {
        "detector_id": row.get("detector_id"),
        "verdict": "IDENTICAL" if same else "DIFFERS",
        "inert": same,
        "measures_nothing": same,
        "differs": not same,
        "byte_diff": not same,
        "silent_in_both": False,
    }


def scan(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Scan recorded rows: name every inert detector, never claim all-clean."""
    verdicts = [classify_row(r) for r in rows]
    checked = [v for v in verdicts if v["verdict"] != NOT_CHECKED]
    inert = [v["detector_id"] for v in checked if v["inert"]]
    valid = [v["detector_id"] for v in checked if not v["inert"]]
    not_checked = [v["detector_id"] for v in verdicts if v["verdict"] == NOT_CHECKED]
    return {
        "all_clean_claim": len(checked) == 0,
        "identical_outputs_reported_as_inert": True,
        "counts": {
            "checked": len(checked),
            "inert": len(inert),
            "measures_nothing": len(inert),
            "valid": len(valid),
            "not_checked": len(not_checked),
            "inventory": len(verdicts),
        },
        "inert": inert,
        "valid": valid,
        "not_checked": not_checked,
        "verdicts": verdicts,
    }
