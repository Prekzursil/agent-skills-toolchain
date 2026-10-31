"""IMP-0189 probe2 (both states): a child failure honours the DECLARED parent
policy, observed in the event log - under continue the sibling child STARTS after
the failure and the meta succeeds; under abort the sibling is SKIPPED and the
meta fails. The default policy is continue.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.compose import (  # noqa: E402
    DEFAULT_FAILURE_POLICY,
    LeafUnit,
    MetaWorkflow,
    Subworkflow,
    execute_composition,
)


def meta_with(policy_a: str) -> MetaWorkflow:
    return MetaWorkflow(
        id="meta",
        budget_micro=45,
        children=(
            Subworkflow(
                id="embed-a",
                budget_micro=30,
                failure_policy=policy_a,
                leaves=(LeafUnit("embed-a.u1", 10, family="timeout"), LeafUnit("embed-a.u2", 20)),
            ),
            Subworkflow(
                id="embed-b",
                budget_micro=15,
                leaves=(LeafUnit("embed-b.u1", 15),),
            ),
        ),
    )


def main() -> int:
    checks = {}

    cont = execute_composition(meta_with("continue"), failing_leaf="embed-a.u1")
    log_c = cont.event_log
    fail_seq = next(e["seq"] for e in log_c if e["kind"] == "failed" and e["node_id"] == "embed-a.u1")
    sib_start_seq = next(e["seq"] for e in log_c if e["kind"] == "started" and e["node_id"] == "embed-b")
    checks["continue_sibling_started_after_failure"] = sib_start_seq > fail_seq
    checks["continue_meta_succeeded"] = any(
        e["kind"] == "succeeded" and e["node_id"] == "meta" for e in log_c
    )
    checks["continue_u2_still_ran"] = any(
        e["kind"] == "succeeded" and e["node_id"] == "embed-a.u2" for e in log_c
    )
    checks["continue_policy_recorded"] = any(
        e["kind"] == "failed" and e["node_id"] == "embed-a" and e["policy"] == "continue"
        for e in log_c
    )

    ab = execute_composition(meta_with("abort"), failing_leaf="embed-a.u1")
    log_a = ab.event_log
    checks["abort_sibling_skipped"] = any(
        e["kind"] == "skipped" and e["node_id"] == "embed-b" and e["policy"] == "abort"
        for e in log_a
    )
    checks["abort_meta_failed"] = any(
        e["kind"] == "failed" and e["node_id"] == "meta" and e["policy"] == "abort"
        for e in log_a
    )
    checks["abort_sibling_never_started"] = not any(
        e["kind"] == "started" and e["node_id"] == "embed-b" for e in log_a
    )

    checks["default_policy_is_continue"] = DEFAULT_FAILURE_POLICY == "continue"
    checks["both_states_diverge"] = (
        cont.status == "ok" and ab.status == "failed"
    )
    checks["no_child_failure_aborts_tree_by_default"] = cont.status == "ok"

    out = {
        "unit_id": "IMP-0189",
        "probe": "probe2-failure-policy",
        "continue_status": cont.status,
        "abort_status": ab.status,
        "continue_event_log": log_c,
        "abort_event_log": log_a,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, indent=1))
    if all(checks.values()):
        print("SUCCESS:IMP-0189-probe2 child failure honours the declared policy in the observed event log: continue keeps the sibling running, abort skips it and fails the meta; default is continue")
        return 0
    print("FAILED:IMP-0189-probe2")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
