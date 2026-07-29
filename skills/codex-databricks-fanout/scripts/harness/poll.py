"""FIVE-clause AND-gate poll (SPEC §5 / section 5). NEVER artifact-count.

`classify` below is a SECOND, complete clause-1-5 gate implementation alongside
`engine.verify.and_gate` (which covers clauses 2-5 only and has NO "UNKNOWN"
verdict). It is still LIVE -- `poll_once` here and the `poll.classify` call in
e2e/smoke_2unit.py both go through it -- so the "one gate impl" claim in
harness/lanes/run_E.py is scoped to run_E's production path, not to this package.
Migrating those call sites onto engine.verify is Roadmap work; until then, do NOT
assume a single gate.

That engine.verify half was UNVERIFIED when this file was merged; it is now SETTLED
by the experiment its own tag named. `engine/` landed with the A00 pure-additions
merge, and `python -c "import engine.verify"` from scripts/ succeeds with
and_gate present -- so BOTH gate implementations are live in this tree and the
"do NOT assume a single gate" warning above applies here in full, not just on the
databricks copy. Migrating the call sites onto engine.verify stays Roadmap work.
(No line number on the smoke_2unit citation on purpose: that call sits at :51 in
the databricks copy and :97 in this one, so a pinned line number is stale by
construction.)
"""

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
    rc, out, _ = run_cmd(
        ["databricks", "jobs", "get-run", str(run_id), "--profile", "bolt-datascience"]
    )
    state = "?"
    try:
        state = (json.loads(out).get("state") or {}).get("life_cycle_state", "?")
    except json.JSONDecodeError:
        pass
    return {u.id: classify(state, u, fetch_artifact(u)) for u in units}
