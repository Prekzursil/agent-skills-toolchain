#!/usr/bin/env python3
"""Probe 1: planted mutant set through the live uniqueness/dedup gate.

Records one accept/reject decision per mutant class. Absence of
unique_ideas.py is measured as accept-all, not skipped as BLOCKED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from probe_common import (  # noqa: E402
    ALL_CLASSES,
    ART,
    UNIT,
    artifact_ok_if_present,
    run_probe1,
)

OUT = HERE / "probe1-live-gate.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    result = run_probe1()
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not result.get("pass"):
        return fail("live matrix or reject-all calibration did not complete")
    classes = [row["class"] for row in result["matrix"]]
    if classes != list(ALL_CLASSES):
        return fail(f"class order {classes}")
    for row in result["matrix"]:
        if row["decision"] not in {"accept", "reject"}:
            return fail(f"{row['class']} missing decision")
    distinct = result["discrimination"]["distinct_accepted"]
    if result["discrimination"]["destroying_brainstorm"] and not result["negative_control"]["fired_on_bad_state"]:
        return fail("reject-all destroying brainstorm was not flagged")
    nc = result["negative_control"]
    if not nc["fired_on_bad_state"] or not nc["silent_on_good_state"]:
        return fail("NC-REJECT-ALL-CALIBRATION both-states failed")
    if result["live_gate"]["quota_skip"].get("skipped") is not True and result["live_gate"]["unique_ideas_exists"] is False:
        return fail("quota unique_idea skip was not observed while unique_ideas.py is absent")
    art_err = artifact_ok_if_present()
    if art_err:
        return fail(art_err)
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        tests = {t["id"]: t.get("result") for t in doc.get("tests") or []}
        if tests.get("T-LIVE-MUTANT-MATRIX") == "NOT-RUN":
            return fail("artifact still has T-LIVE-MUTANT-MATRIX NOT-RUN")
        if tests.get("T-DISTINCT-LIVE-CONTROL") == "NOT-RUN":
            return fail("artifact still has T-DISTINCT-LIVE-CONTROL NOT-RUN")
    print(json.dumps(
        {
            "probe": result["probe"],
            "live_kind": result["live_gate"]["kind"],
            "unique_ideas_exists": result["live_gate"]["unique_ideas_exists"],
            "quota_skipped": result["live_gate"]["quota_skip"].get("skipped"),
            "decisions": {row["class"]: row["decision"] for row in result["matrix"]},
            "distinct_accepted": distinct,
            "recall_on_gaming_classes": result["discrimination"]["recall_on_gaming_classes"],
            "gaming_succeeds": result["discrimination"]["gaming_succeeds"],
            "verdict": result["verdict"],
            "negative_control": {
                "fired_on_bad_state": nc["fired_on_bad_state"],
                "silent_on_good_state": nc["silent_on_good_state"],
            },
        },
        indent=2,
        sort_keys=True,
    ))
    print(
        "SUCCESS:ADV-0096-probe1 live gate matrix "
        f"kind={result['live_gate']['kind']} "
        f"gaming_recall={result['discrimination']['recall_on_gaming_classes']} "
        f"distinct={result['discrimination']['distinct_decision']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
