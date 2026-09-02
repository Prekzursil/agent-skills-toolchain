#!/usr/bin/env python3
"""Named probe 1: a trace-derived workflow replays the ad-hoc outcome.

Both-states:
  good — same inputs reproduce the recorded digest/verdict
  bad  — mutated inputs and a dropped stage each diverge
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from workflow_foundry.generate import from_trace  # noqa: E402
from workflow_foundry.replay import outcomes_equal, replay_workflow  # noqa: E402
from workflow_foundry.replay_log import record_adhoc  # noqa: E402
from workflow_foundry.sample import SAMPLE_INPUTS, SAMPLE_STEPS  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0194-probe1 {msg}")
    return 1


def main() -> int:
    log = record_adhoc(SAMPLE_INPUTS, SAMPLE_STEPS, trace_id="imp0194-adhoc")
    wf = from_trace(log)
    same = replay_workflow(wf, log["inputs"])
    mutated_inputs = dict(SAMPLE_INPUTS)
    mutated_inputs["a"] = "goodbye"
    different = replay_workflow(wf, mutated_inputs)
    trimmed = copy.deepcopy(wf)
    trimmed["stages"] = list(trimmed["stages"])[:-1]
    trimmed["stop_rule"]["max_stages"] = len(trimmed["stages"])
    dropped = replay_workflow(trimmed, log["inputs"])

    leaked = []
    allowed = set(wf["tools"]) | set(SAMPLE_INPUTS.values()) | set(SAMPLE_INPUTS)
    for event in log["events"]:
        allowed.update(event["args"])
        allowed.add(event["output"])
        allowed.add(event["stage_id"])

    def string_values(node: object) -> list[str]:
        found: list[str] = []
        if isinstance(node, str):
            found.append(node)
        elif isinstance(node, dict):
            for value in node.values():
                found.extend(string_values(value))
        elif isinstance(node, list):
            for value in node:
                found.extend(string_values(value))
        return found

    present = set(string_values(wf))
    for event in log["events"]:
        result = event["result"]
        if result not in allowed and result in present:
            leaked.append(result)

    payload = {
        "probe": "probe1-trace-replay",
        "unit_id": "IMP-0194",
        "trace_id": log["trace_id"],
        "stages": len(wf["stages"]),
        "same_inputs_equal": outcomes_equal(same["outcome"], log["outcome"]),
        "mutated_inputs_equal": outcomes_equal(different["outcome"], log["outcome"]),
        "dropped_stage_equal": outcomes_equal(dropped["outcome"], log["outcome"]),
        "applies_match_spawns": same["applies"] == log["spawns"],
        "recorded_digest": log["outcome"]["digest"],
        "replayed_digest": same["outcome"]["digest"],
        "leaked_results": leaked,
        "workflow_id": wf["id"],
    }
    payload["pass"] = bool(
        payload["same_inputs_equal"]
        and not payload["mutated_inputs_equal"]
        and not payload["dropped_stage_equal"]
        and payload["applies_match_spawns"]
        and not leaked
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["same_inputs_equal"]:
        return fail("replay digest/verdict != recorded ad-hoc outcome")
    if payload["mutated_inputs_equal"]:
        return fail("mutated inputs still matched (outcome not input-sensitive)")
    if payload["dropped_stage_equal"]:
        return fail("dropped stage still matched (stages not load-bearing)")
    if not payload["applies_match_spawns"]:
        return fail("replay applies != recorded spawns")
    if leaked:
        return fail(f"result strings copied into workflow: {leaked}")
    print("SUCCESS:IMP-0194-probe1 trace-derived workflow replays ad-hoc outcome")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
