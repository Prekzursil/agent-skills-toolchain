#!/usr/bin/env python3
"""Named probe 1: an intentional empty case is FLAGGED, not scored.

Both-states: a mutant that stamps score=0 on empty input produces a
meaningless green. The live gate must omit score and set status=FLAGGED.
A control case above the declared floor is SCORED and records byte/item
counts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.nonempty import (  # noqa: E402
    DECLARED_FLOOR,
    STATUS_FLAGGED,
    STATUS_SCORED,
    below_floor_case,
    control_case,
    empty_case,
    load_case,
    mutant_score_empty,
    payload_bytes,
    result_schema_errors,
    run_case,
)

UNIT = "TST-0230"
RAW = HERE / "probe1-empty-flagged.raw.json"
FIXTURES = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def as_case(path: Path) -> dict:
    doc = load_case(path)
    doc["payload"] = payload_bytes(doc)
    return doc


def main() -> int:
    planted = as_case(FIXTURES / "empty.json")
    live_empty = run_case(planted)
    if live_empty.get("status") != STATUS_FLAGGED:
        return fail(f"empty case status={live_empty.get('status')} not FLAGGED")
    if "score" in live_empty:
        return fail("empty case carried a score (must be omitted, not zero)")
    if live_empty.get("reason_id") != "empty-input":
        return fail(f"empty reason_id={live_empty.get('reason_id')}")
    if live_empty.get("input_bytes") != 0:
        return fail(f"empty input_bytes was not recorded as 0: {live_empty.get('input_bytes')}")
    if live_empty.get("input_items") != 0:
        return fail(f"empty input_items was not recorded as 0: {live_empty.get('input_items')}")
    errs = result_schema_errors(live_empty)
    if errs:
        return fail(f"empty row schema {errs}")

    mutant = mutant_score_empty(planted)
    if mutant.get("status") != STATUS_SCORED or mutant.get("score") != 0:
        return fail(f"mutant did not score empty as 0: {mutant}")
    if live_empty.get("status") == mutant.get("status"):
        return fail("live and mutant agreed on empty (detector is inert)")

    generated_empty = run_case(empty_case())
    if generated_empty.get("status") != STATUS_FLAGGED or "score" in generated_empty:
        return fail("empty_case() helper was scored")

    tiny = as_case(FIXTURES / "below-floor.json")
    live_tiny = run_case(tiny)
    if live_tiny.get("status") != STATUS_FLAGGED:
        return fail("below-floor case was scored")
    if "score" in live_tiny:
        return fail("below-floor case carried a score")
    if live_tiny.get("reason_id") != "below-floor":
        return fail(f"below-floor reason_id={live_tiny.get('reason_id')}")
    if int(live_tiny["input_bytes"]) >= int(DECLARED_FLOOR["min_bytes"]):
        return fail("below-floor fixture is not below the declared byte floor")
    helper_tiny = run_case(below_floor_case())
    if helper_tiny.get("status") != STATUS_FLAGGED:
        return fail("below_floor_case() was scored")

    control_doc = as_case(FIXTURES / "control.json")
    live_ctrl = run_case(control_doc)
    if live_ctrl.get("status") != STATUS_SCORED:
        return fail(f"control fixture status={live_ctrl.get('status')}")
    if "score" not in live_ctrl:
        return fail("control fixture omitted score")
    if int(live_ctrl["input_bytes"]) < int(DECLARED_FLOOR["min_bytes"]):
        return fail("control fixture input_bytes below floor")
    if int(live_ctrl["input_items"]) < int(DECLARED_FLOOR["min_items"]):
        return fail("control fixture input_items below floor")
    ctrl_errs = result_schema_errors(live_ctrl)
    if ctrl_errs:
        return fail(f"control row schema {ctrl_errs}")

    fat = run_case(control_case())
    if fat.get("status") != STATUS_SCORED:
        return fail("64KiB control case was not scored")
    if int(fat["input_bytes"]) != 65536:
        return fail(f"control_case bytes={fat['input_bytes']}")
    if int(fat["elapsed_ns"]) <= 0:
        return fail("control elapsed_ns was not positive")

    payload = {
        "pass": True,
        "probe": "probe1-empty-flagged-not-scored",
        "unit_id": UNIT,
        "floor": DECLARED_FLOOR,
        "empty": {
            "status": live_empty["status"],
            "reason_id": live_empty["reason_id"],
            "input_bytes": live_empty["input_bytes"],
            "input_items": live_empty["input_items"],
            "score_present": "score" in live_empty,
        },
        "below_floor": {
            "status": live_tiny["status"],
            "reason_id": live_tiny["reason_id"],
            "input_bytes": live_tiny["input_bytes"],
            "score_present": "score" in live_tiny,
        },
        "control": {
            "status": live_ctrl["status"],
            "input_bytes": live_ctrl["input_bytes"],
            "input_items": live_ctrl["input_items"],
            "score": live_ctrl["score"],
            "elapsed_ns": live_ctrl["elapsed_ns"],
        },
        "mutant_scores_empty": mutant.get("status") == STATUS_SCORED,
        "mutant_score": mutant.get("score"),
        "live_disagrees_with_mutant": live_empty.get("status") != mutant.get("status"),
        "both_states": True,
    }
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        f"empty={live_empty['status']} tiny={live_tiny['status']} "
        f"control={live_ctrl['status']} mutant_scores_empty=True "
        f"live_disagrees=True"
    )
    print("SUCCESS:TST-0230-probe1 empty case FLAGGED not scored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
