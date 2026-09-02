#!/usr/bin/env python3
"""Named probe 2: workflow retry exhaustion does not multiply dispatch attempts.

Signal (2) of IMP-0140. Ledger counts are read from recorded events, not inferred
from the policy integer. A rival that funnels every failure through plan_retry
must raise the dispatch count (both-states).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.retry import (  # noqa: E402
    DISPATCH_RETRY_REASONS,
    plan_retry,
)
from agentspec.workflow_retry import (  # noqa: E402
    DispatchLedger,
    WorkflowRetryPolicy,
    exhaust_workflow_retries,
    plan_workflow_retry,
    rival_multiply_via_plan_retry,
)


def main() -> int:
    fixture = json.loads(
        (HERE / "fixtures" / "exhaust_workflow.json").read_text(encoding="utf-8")
    )
    reason = str(fixture["reason"])
    max_attempts = int(fixture["workflow_max_attempts"])
    if reason in DISPATCH_RETRY_REASONS:
        print(
            "FAILED:IMP-0140-probe2 fixture reason is a dispatch reason; would not isolate layers"
        )
        return 1

    policy = WorkflowRetryPolicy(max_attempts=max_attempts)
    ledger = DispatchLedger()

    seed = plan_workflow_retry(
        reason="win-arg-limit",
        workflow_failures=0,
        policy=policy,
        ledger=ledger,
        dispatch_failures=0,
    )
    if seed.layer != "dispatch" or seed.dispatch_plan is None:
        print("FAILED:IMP-0140-probe2 win-arg-limit did not CALL plan_retry")
        return 1
    dispatch_after_seed = ledger.dispatch_attempt_count()
    if dispatch_after_seed < 1:
        print(
            "FAILED:IMP-0140-probe2 dispatch attempts not counted after plan_retry call"
        )
        return 1
    # Direct rail: retry once then stop. Counted, not inferred.
    second = plan_retry("win-arg-limit", attempt=2)
    if second.retry:
        print("FAILED:IMP-0140-probe2 win-arg-limit retried more than once")
        return 1

    dispatch_before_exhaust = ledger.dispatch_attempt_count()
    result = exhaust_workflow_retries(reason, policy, ledger)
    dispatch_after = result["dispatch_after"]
    workflow_attempts = result["workflow_attempts"]

    if dispatch_after != dispatch_before_exhaust:
        print(
            "FAILED:IMP-0140-probe2 dispatch attempts changed "
            f"{dispatch_before_exhaust} -> {dispatch_after}"
        )
        return 1
    if result["dispatch_before"] != dispatch_before_exhaust:
        print("FAILED:IMP-0140-probe2 exhaust did not snapshot the live ledger count")
        return 1
    if workflow_attempts != max_attempts:
        print(
            f"FAILED:IMP-0140-probe2 workflow_attempts={workflow_attempts} "
            f"want={max_attempts} (counted from ledger)"
        )
        return 1
    if not result["last_exhausted"]:
        print("FAILED:IMP-0140-probe2 workflow budget did not exhaust")
        return 1
    if result["last_layer"] != "workflow":
        print(f"FAILED:IMP-0140-probe2 last layer {result['last_layer']}")
        return 1

    rival_ledger = DispatchLedger()
    rival = rival_multiply_via_plan_retry(reason, policy, rival_ledger)
    if rival["dispatch_after"] <= rival["dispatch_before"]:
        print("FAILED:IMP-0140-probe2 rival did not raise dispatch attempts")
        return 1
    if rival["dispatch_after"] < max_attempts + 1:
        print(f"FAILED:IMP-0140-probe2 rival count too small {rival}")
        return 1

    out = {
        "pass": True,
        "probe": "probe2-ledger-exhaustion",
        "unit_id": "IMP-0140",
        "fixture": fixture["id"],
        "reason": reason,
        "seed_layer": seed.layer,
        "dispatch_after_seed": dispatch_after_seed,
        "dispatch_before_exhaust": dispatch_before_exhaust,
        "dispatch_after_exhaust": dispatch_after,
        "dispatch_unchanged": dispatch_after == dispatch_before_exhaust,
        "workflow_attempts_counted": workflow_attempts,
        "policy_max_attempts": max_attempts,
        "ledger_dispatch_events": ledger.count("dispatch", "attempt"),
        "ledger_workflow_events": ledger.count("workflow", "attempt"),
        "rival_dispatch_after": rival["dispatch_after"],
        "both_states": {
            "silent_on_good": dispatch_after == dispatch_before_exhaust,
            "fired_on_bad": rival["dispatch_after"] > rival["dispatch_before"],
        },
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "dispatch_before={b} dispatch_after={a} equal={eq} "
        "workflow_attempts={w} rival_dispatch={r}".format(
            b=dispatch_before_exhaust,
            a=dispatch_after,
            eq=dispatch_after == dispatch_before_exhaust,
            w=workflow_attempts,
            r=rival["dispatch_after"],
        )
    )
    print("SUCCESS:IMP-0140-probe2 ledger count equality under workflow exhaustion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
