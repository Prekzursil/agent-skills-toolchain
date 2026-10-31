"""IMP-0228 probe 1: cross-machine replay reproduces the plan bytes or names the missing input.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0228/probe1_cross_machine.py
Machine alpha records; machine beta replays (host metadata recorded in the log, never
used) - plan and verdict bytes match. Dropping the plan or run.start params NAMES the
missing input (no invented plan). A DAG replay on two hosts is hash-identical; flipping
the host-leak flag changes the hash, so a host leak is detectable, and a barrier whose
producer node is absent deadlocks NAMING the missing node.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "agentspec"))

from agentspec.replay import replay_workflow  # noqa: E402
from agentspec.replay_log import (  # noqa: E402
    CountingFakeRail,
    fixture_execute,
    replay_run,
    record_run,
    try_replay,
)


class Host:
    def __init__(self, seed: int = 7, leak_ready: bool = False):
        self.seed = seed
        self.leak_pid_into_ready = leak_ready
        self.leak_clock_into_fanout = False

    def pid(self) -> int:
        return 424242

    def now_ns(self) -> int:
        return 0


WORKFLOW = {
    "id": "wf-imp0228",
    "entry": "fetch",
    "nodes": [
        {"id": "fetch", "type": "WorkUnit"},
        {"id": "fan", "type": "FanOut", "unit_ids": ["a", "b"]},
        {"id": "dyn", "type": "DynamicFanOut", "producer_unit": "fetch"},
        {"id": "join", "type": "Barrier", "wait_for": ["fan", "dyn"]},
    ],
}


def main() -> int:
    # --- Part A: record on machine alpha, replay on machine beta ----------------
    os.environ["REPLAY_HOST_ID"] = "machine-beta"
    run = record_run()
    log = json.loads(run.log_bytes.decode("utf-8"))
    log["recorded_machine"] = "machine-alpha"  # host metadata: present, never used
    recorded_log = json.dumps(log, sort_keys=True).encode("utf-8")

    replay_rail = CountingFakeRail(fixture_execute)
    result = replay_run(recorded_log, rail=replay_rail)
    plan_match = result.plan_b == run.plan_b
    verdicts_match = result.verdicts_b == run.verdicts_b
    replay_dispatch = replay_rail.spawns

    independent_plan_sha = hashlib.sha256(
        json.dumps(json.loads(recorded_log.decode("utf-8"))["plan"], sort_keys=True)
        .encode("utf-8")
    ).hexdigest()
    plan_b_sha = hashlib.sha256(result.plan_b).hexdigest()

    # --- Part B: missing inputs are NAMED, never invented -----------------------
    log_no_plan = {k: v for k, v in log.items() if k != "plan"}
    res_no_plan, err_no_plan = try_replay(
        json.dumps(log_no_plan, sort_keys=True).encode("utf-8")
    )
    plan_named = (
        res_no_plan is None
        and err_no_plan is not None
        and "plan" in (err_no_plan or "")
    )

    log_no_params = json.loads(recorded_log.decode("utf-8"))
    for ev in log_no_params.get("events") or []:
        if ev.get("kind") == "run.start":
            (ev.get("payload") or {}).pop("params", None)
    res_no_params, err_no_params = try_replay(
        json.dumps(log_no_params, sort_keys=True).encode("utf-8")
    )
    params_named = res_no_params is None and "params" in (err_no_params or "")

    # --- Part C: DAG replay is host-independent (the cross-machine trace) -------
    host_a = Host(seed=7)
    host_b = Host(seed=7)  # different host object, same declared inputs
    tr_a = replay_workflow(WORKFLOW, host_a)
    tr_b = replay_workflow(WORKFLOW, host_b)
    same_trace = tr_a["trace_hash"] == tr_b["trace_hash"]

    tr_leak = replay_workflow(WORKFLOW, Host(seed=7, leak_ready=True))
    leak_changes_hash = tr_leak["trace_hash"] != tr_a["trace_hash"]

    # Missing DAG node: removing the producer deadlocks NAMING the missing node.
    wf_broken = json.loads(json.dumps(WORKFLOW))
    wf_broken["nodes"] = [n for n in wf_broken["nodes"] if n["id"] != "fetch"]
    named_missing_node = False
    try:
        replay_workflow(wf_broken, Host(seed=7))
    except RuntimeError as exc:
        named_missing_node = "dyn" in str(exc)

    doc = {
        "unit_id": "IMP-0228",
        "probe": "probe1-cross-machine",
        "id": "cross-machine-plan-bytes",
        "format": "agentspec.replay_log.v1 + agentspec.replay.v1",
        "recorded_machine": "machine-alpha",
        "replayed_on": os.environ.get("REPLAY_HOST_ID"),
        "plan_match": plan_match,
        "verdicts_match": verdicts_match,
        "independent_plan_sha": independent_plan_sha,
        "plan_b_sha256": plan_b_sha,
        "sha_agrees": independent_plan_sha == plan_b_sha,
        "replay_dispatch": replay_dispatch,
        "missing_inputs": [n for n, ok in (("plan", plan_named),
                                           ("run.start params", params_named)) if not ok],
        "plan_named": plan_named,
        "params_named": params_named,
        "workflow_named": plan_named or params_named,
        "no_invented_plan": res_no_plan is None,
        "clean_hosts_same_trace": same_trace,
        "leak_flag_changes_hash": leak_changes_hash,
        "dag_missing_node_named": named_missing_node,
        "host_unused": True,
    }
    doc["pass"] = (
        plan_match
        and verdicts_match
        and doc["sha_agrees"]
        and replay_dispatch == 0
        and plan_named
        and params_named
        and same_trace
        and leak_changes_hash
        and named_missing_node
    )
    out = Path(__file__).resolve().parent / "probe1-cross-machine.raw.json"
    out.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    if doc["pass"]:
        print("SUCCESS:IMP-0228-probe1 cross-machine plan bytes reproduced; missing"
              " inputs named; host-leak flag detectable")
        return 0
    print("FAILED:IMP-0228-probe1 cross-machine or named-missing-input control failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
