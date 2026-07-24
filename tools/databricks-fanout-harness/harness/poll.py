"""FIVE-clause AND-gate poll (SPEC §5). NEVER artifact-count."""
from __future__ import annotations
import json
from harness.contract import Unit, and_gate_artifact, schema_valid, floor_for

_TERMINAL = {"TERMINATED", "INTERNAL_ERROR", "SKIPPED"}

def classify(job_state: str, unit: Unit, local_artifact) -> str:
    if job_state not in _TERMINAL:
        return "RUNNING"
    if local_artifact is None:
        return "FAILED"
    ok, reason, _ = and_gate_artifact(unit.id, local_artifact, floor_for(unit.lane))
    if not ok:
        return "UNKNOWN" if reason.startswith("unreadable") else "FAILED"
    sok, _ = schema_valid(unit, local_artifact)
    return "DONE" if sok else "FAILED"

def poll_once(run_id, units, run_cmd, fetch_artifact) -> dict:
    rc, out, _ = run_cmd(["databricks", "jobs", "get-run", str(run_id), "--profile", "bolt-datascience"])
    state = "?"
    try:
        state = (json.loads(out).get("state") or {}).get("life_cycle_state", "?")
    except json.JSONDecodeError:
        pass
    return {u.id: classify(state, u, fetch_artifact(u)) for u in units}
