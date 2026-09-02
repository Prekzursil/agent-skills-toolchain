"""Two-state campaign over every shipped detector (IMP-0471).

Each census detector is exercised through its known-good / known-broken
adapter. Detectors without a known-broken fixture are surfaced loudly as
NOT-CHECKED, never silently skipped or silently passed.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from detectors.adapters import ADAPTERS
from detectors.census import (
    KNOWN_PRESENT_DETECTOR,
    census_detector_ids,
    enumerator_control,
)
from detectors.two_state import (
    VERDICT_NOT_CHECKED,
    VERDICT_SILENT_BOTH,
    harness_self_test,
    run_two_state,
)

QUESTION = (
    "For every shipped detector: is it silent on the known-good state and "
    "does it fire on the known-broken state (two-state validated), or is it "
    "silent in both states / unchecked?"
)


def _row(detector_id: str) -> dict[str, Any]:
    adapter = ADAPTERS.get(detector_id)
    rec = run_two_state(adapter, detector_id=detector_id)
    return {
        "detector_id": detector_id,
        "verdict": rec.verdict,
        "valid": rec.valid,
        "reason": rec.reason,
        "good_output": rec.good,
        "broken_output": rec.broken,
        "has_known_broken_fixture": adapter is not None,
        "silent_in_both": rec.verdict == VERDICT_SILENT_BOTH,
    }


def run_campaign() -> dict[str, Any]:
    ids = census_detector_ids()
    table = [_row(det_id) for det_id in ids]
    verdict_counts = dict(Counter(r["verdict"] for r in table))
    silent_ids = sorted(r["detector_id"] for r in table if r["silent_in_both"])
    not_checked_ids = sorted(
        r["detector_id"] for r in table if r["verdict"] == VERDICT_NOT_CHECKED
    )
    answer = {
        "shipped_count": len(table),
        "checked_count": len(table) - len(not_checked_ids),
        "silent_in_both_count": len(silent_ids),
        "silent_in_both_ids": silent_ids,
        "not_checked_count": len(not_checked_ids),
        "not_checked_ids": not_checked_ids,
    }
    return {
        "question": QUESTION,
        "answer": answer,
        "table": table,
        "verdict_counts": verdict_counts,
        "enumerator": enumerator_control(),
        "known_present_detector": KNOWN_PRESENT_DETECTOR,
        "harness_self_test": harness_self_test(),
    }
