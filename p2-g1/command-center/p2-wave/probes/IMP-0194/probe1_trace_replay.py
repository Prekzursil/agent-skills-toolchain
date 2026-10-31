"""IMP-0194 probe 1 (source): a workflow compiled from a successful ad-hoc replay
log recomputes the SAME outcome digest on the same inputs; mutated inputs and a
dropped stage each diverge; result strings are not copied into the workflow doc.

Exit 0 iff all four states hold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(W / "tools"))
from workflow_foundry.sample import SAMPLE_INPUTS, SAMPLE_STEPS  # noqa: E402
from workflow_foundry.replay_log import record_adhoc  # noqa: E402
from workflow_foundry.generate import from_trace  # noqa: E402
from workflow_foundry.replay import replay_workflow, outcomes_equal  # noqa: E402

RAW = HERE / "probe1-trace-replay.raw.txt"

log = record_adhoc(SAMPLE_INPUTS, SAMPLE_STEPS, trace_id="imp0194-adhoc")
wf = from_trace(log)

same = replay_workflow(wf, SAMPLE_INPUTS)
mutated_inputs = dict(SAMPLE_INPUTS, b="w0rld")
mut = replay_workflow(wf, mutated_inputs)
ablated = {"id": wf["id"] + "-ablated",
           "stages": wf["stages"][:-1], "tools": wf.get("tools", [])}
drop = replay_workflow(ablated, SAMPLE_INPUTS)

same_inputs_equal = outcomes_equal(same["outcome"], log["outcome"])
mutated_inputs_equal = outcomes_equal(mut["outcome"], log["outcome"])
dropped_stage_equal = outcomes_equal(drop["outcome"], log["outcome"])
leaked = [e["result"] for e in log["events"]
          if json.dumps(e["result"]) in json.dumps(wf)]

lines = [json.dumps({"probe": "probe1-trace-replay", "unit_id": "IMP-0194",
                     "trace_id": log["trace_id"], "workflow_id": wf["id"],
                     "stages": len(wf["stages"]),
                     "recorded_digest": log["outcome"]["digest"],
                     "replayed_digest": same["outcome"]["digest"],
                     "same_inputs_equal": same_inputs_equal,
                     "mutated_inputs_equal": mutated_inputs_equal,
                     "dropped_stage_equal": dropped_stage_equal,
                     "applies_match_spawns": wf.get("tools") == log["spawns"],
                     "leaked_results": leaked, "pass": True})]
assert same_inputs_equal, "same-input replay diverged from the recorded digest"
assert not mutated_inputs_equal, "mutated inputs reproduced the recorded digest"
assert not dropped_stage_equal, "dropped stage changed nothing: stage decorative"
assert wf.get("tools") == log["spawns"], "generated applies do not match the trace spawns"
assert not leaked, "result strings leaked into the workflow document"
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"same_inputs_equal": True,
                              "mutated_inputs_diverge": True,
                              "dropped_stage_diverges": True,
                              "leaked_results": 0,
                              "recorded": log["outcome"]["digest"][:16],
                              "replayed": same["outcome"]["digest"][:16]}))
print("SUCCESS:IMP-0194-probe1 trace-derived workflow replays ad-hoc outcome")
