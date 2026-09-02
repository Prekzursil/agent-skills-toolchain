#!/usr/bin/env python3
"""Probe 1: re-run the planted-skip detector control.

Adds a skip marker to a failing test and requires the diff to see it as a
newly skipped, no-longer-executed id. Re-executes the fixture; does not
take the artifact's verdict as proof.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from runner import PLANTED_REASON  # noqa: E402
from skip_diff import payload_from_receipt, run_planted_skip_control  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0060-skip-count-diff.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0060-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0060":
        print("FAILED:CNF-0060-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:CNF-0060" not in text:
        print("FAILED:CNF-0060-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0060-probe1 self-declared", st)
        return 1

    ctrl = run_planted_skip_control()
    planted = ctrl["planted_id"]
    disabled = ctrl["disabled"]
    before_ids = list(ctrl["before"]["executed_ids"])
    after_ids = list(ctrl["after"]["executed_ids"])
    payload = {
        "probe": "probe1-planted-skip",
        "unit_id": "CNF-0060",
        "pass": bool(ctrl["fired"]),
        "planted_id": planted,
        "newly_skipped": disabled["newly_skipped"],
        "stopped_executing": disabled["stopped_executing"],
        "executed_count_before": disabled["executed_count_before"],
        "executed_count_after": disabled["executed_count_after"],
        "passed_count_unchanged": disabled["passed_count_unchanged"],
        "executed_ids_before": before_ids,
        "executed_ids_after": after_ids,
    }
    print(json.dumps(payload, sort_keys=True))
    if not ctrl["fired"]:
        print("FAILED:CNF-0060-probe1 planted skip was not detected")
        return 1
    if planted not in disabled["newly_skipped"]:
        print("FAILED:CNF-0060-probe1 planted id not in newly_skipped")
        return 1
    if planted not in disabled["stopped_executing"]:
        print("FAILED:CNF-0060-probe1 planted id still executed")
        return 1
    if planted in after_ids or planted not in before_ids:
        print("FAILED:CNF-0060-probe1 executed-id sets do not show the drop")
        return 1
    if disabled["executed_count_after"] != disabled["executed_count_before"] - 1:
        print("FAILED:CNF-0060-probe1 executed count did not drop by 1")
        return 1
    just = next(j for j in disabled["justifications"] if j["id"] == planted)
    if PLANTED_REASON not in (just.get("justification") or ""):
        print("FAILED:CNF-0060-probe1 planted reason missing", just)
        return 1
    attached = payload_from_receipt(doc)
    art_ctrl = attached["planted_skip"]
    if art_ctrl.get("fired") is not True:
        print("FAILED:CNF-0060-probe1 artifact did not record fired=true")
        return 1
    if not attached["executed_ids_before"]:
        print("FAILED:CNF-0060-probe1 artifact missing before executed_ids")
        return 1
    if not attached["executed_ids_after"]:
        print("FAILED:CNF-0060-probe1 artifact missing after executed_ids")
        return 1
    print(
        "planted",
        planted,
        "newly_skipped",
        disabled["newly_skipped"],
        "executed",
        disabled["executed_count_before"],
        "->",
        disabled["executed_count_after"],
        "passed_unchanged",
        disabled["passed_count_unchanged"],
    )
    print("SUCCESS:CNF-0060-probe1 planted skip detected; both executed-id sets attached")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
