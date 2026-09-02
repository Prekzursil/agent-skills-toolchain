#!/usr/bin/env python3
"""Probe 1: per-detector two-state table for every shipped detector."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "detectors" / "tests"))

from detectors.campaign import run_campaign  # noqa: E402
from detectors.census import KNOWN_PRESENT_DETECTOR  # noqa: E402
from detectors.two_state import (  # noqa: E402
    VERDICT_DIFFERS,
    VERDICT_ERROR,
    VERDICT_NOT_CHECKED,
    VERDICT_SILENT_BOTH,
)
from test_two_state_harness import run_all  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0471.json"
SENTINEL = "SENTINEL:IMP-0471:DETECTORS-TWO-STATE-VALIDATED"


def main() -> int:
    tests = run_all()
    campaign = run_campaign()
    answer = campaign["answer"]
    enum = campaign["enumerator"]
    table = campaign["table"]

    summary = {
        "probe": "probe1-two-state-table",
        "unit_id": "IMP-0471",
        "shipped_count": answer["shipped_count"],
        "checked_count": answer["checked_count"],
        "silent_in_both_count": answer["silent_in_both_count"],
        "silent_in_both_ids": answer["silent_in_both_ids"],
        "not_checked_count": answer["not_checked_count"],
        "not_checked_ids": answer["not_checked_ids"],
        "verdict_counts": campaign["verdict_counts"],
        "enumerator_found_known": enum["found_known_present"],
        "harness_self_test": campaign["harness_self_test"]["pass"],
        "unit_tests": tests,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    if not enum["found_known_present"]:
        print("FAILED:IMP-0471-probe1 enumerator missed", KNOWN_PRESENT_DETECTOR)
        return 1
    if not campaign["harness_self_test"]["pass"]:
        print("FAILED:IMP-0471-probe1 harness self-test")
        return 1
    if answer["shipped_count"] < 1:
        print("FAILED:IMP-0471-probe1 empty census")
        return 1

    for row in table:
        verdict = row["verdict"]
        if verdict == VERDICT_ERROR:
            print("FAILED:IMP-0471-probe1 detector error", row["detector_id"], row.get("reason"))
            return 1
        if row["has_known_broken_fixture"] is False and verdict != VERDICT_NOT_CHECKED:
            print("FAILED:IMP-0471-probe1 missing fixture not NOT-CHECKED", row["detector_id"])
            return 1
        if verdict == VERDICT_NOT_CHECKED and row.get("good_output") is not None:
            print("FAILED:IMP-0471-probe1 NOT-CHECKED leaked outputs", row["detector_id"])
            return 1
        if verdict == VERDICT_SILENT_BOTH and not row["silent_in_both"]:
            print("FAILED:IMP-0471-probe1 SILENT-BOTH flag mismatch", row["detector_id"])
            return 1
        if verdict == VERDICT_DIFFERS:
            good = row.get("good_output") or {}
            broken = row.get("broken_output") or {}
            if good.get("fired") or not broken.get("fired"):
                print("FAILED:IMP-0471-probe1 DIFFERS polarity", row["detector_id"])
                return 1

    fs = next(
        (r for r in table if r["detector_id"].endswith("filesystem_only_verdict")),
        None,
    )
    if fs is not None and fs["verdict"] == VERDICT_DIFFERS:
        print("FAILED:IMP-0471-probe1 filesystem-only must not discriminate")
        return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print("FAILED:IMP-0471-probe1 self-declared", st)
            return 1
        if SENTINEL not in text:
            print("FAILED:IMP-0471-probe1 sentinel-absent")
            return 1

    print(
        f"silent_in_both={answer['silent_in_both_count']}/"
        f"{answer['shipped_count']} not_checked={answer['not_checked_count']}"
    )
    print("SUCCESS:IMP-0471-probe1 two-state table for every shipped detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
