#!/usr/bin/env python3
"""Probe 1: never-converging predicate stops at the bound (both-states twin).

Catalog tests_required[0]: never-converging predicate stops at the bound
(both-states with a converging twin).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(REPO / "tools" / "agentrail"))

from agentrail.runner import (  # noqa: E402
    Loop,
    LoopError,
    execute_loop,
    loop_result_to_dict,
)
from scenario import (  # noqa: E402
    BOUND,
    CONVERGE_AT,
    INITIAL,
    converging_loop,
    fail_on_bound_loop,
    never_loop,
)

OUT = HERE / "probe1-bound.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0216-probe1 {msg}")
    return 1


def main() -> int:
    never = execute_loop(never_loop(), INITIAL)
    conv = execute_loop(converging_loop(), INITIAL)
    failed = execute_loop(fail_on_bound_loop(), INITIAL)

    if never.status != "BOUND_REACHED" or never.converged:
        return fail(f"never status={never.status} converged={never.converged}")
    if len(never.iterations) != BOUND:
        return fail(f"never iterations={len(never.iterations)} want={BOUND}")
    if any(rec.predicate_verdict for rec in never.iterations):
        return fail("never-converging twin recorded a True verdict")
    if never.final_state.get("n") != BOUND:
        return fail(f"never final n={never.final_state.get('n')} want={BOUND}")
    if never.bound != BOUND:
        return fail(f"never bound field={never.bound}")

    if conv.status != "CONVERGED" or not conv.converged:
        return fail(f"twin status={conv.status} converged={conv.converged}")
    if len(conv.iterations) != CONVERGE_AT:
        return fail(f"twin iterations={len(conv.iterations)} want={CONVERGE_AT}")
    if len(conv.iterations) >= BOUND:
        return fail("converging twin ran to the bound — both-states collapsed")
    if not conv.iterations[-1].predicate_verdict:
        return fail("converging twin last verdict is False")
    if any(rec.predicate_verdict for rec in conv.iterations[:-1]):
        return fail("converging twin True before the threshold")
    if conv.final_state.get("n") != CONVERGE_AT:
        return fail(f"twin final n={conv.final_state.get('n')} want={CONVERGE_AT}")
    last_inputs = conv.iterations[-1].predicate_inputs
    if last_inputs.get("bindings", {}).get("n") != CONVERGE_AT:
        return fail(f"converging twin did not record n={CONVERGE_AT} in predicate inputs")

    if failed.status != "FAILED_BOUND" or failed.converged:
        return fail(f"on_bound_reached=fail status={failed.status}")
    if len(failed.iterations) != BOUND:
        return fail("fail-on-bound did not stop at the bound")

    try:
        Loop(
            id="unbounded",
            body=({"op": "noop"},),
            convergence_expr=None,
            max_iterations=None,
        )
        return fail("unbounded Loop was representable")
    except LoopError as exc:
        if exc.code != "loop-unbounded":
            return fail(f"unbounded raised {exc.code}")

    try:
        execute_loop(
            Loop(
                id="expr-only",
                body=({"op": "noop"},),
                convergence_expr={"op": "never"},
                max_iterations=None,
            ),
            {},
        )
        return fail("expr-only never-predicate executed without a runtime bound")
    except LoopError as exc:
        if exc.code != "loop-bound-required-at-runtime":
            return fail(f"expr-only raised {exc.code}")

    doc = {
        "pass": True,
        "probe": "probe1-never-converge-bound",
        "unit_id": "IMP-0216",
        "never": loop_result_to_dict(never),
        "converging_twin": loop_result_to_dict(conv),
        "fail_on_bound": {"status": failed.status, "iteration_count": len(failed.iterations)},
        "unbounded_rejected": True,
        "expr_only_hang_rejected": True,
        "both_states": {
            "never_stopped_at_bound": True,
            "twin_converged_before_bound": True,
            "shared_body": "incr n by 1",
            "shared_bound": BOUND,
        },
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"never_iters={len(never.iterations)} never_status={never.status} "
        f"twin_iters={len(conv.iterations)} twin_status={conv.status} "
        f"fail_status={failed.status}"
    )
    print("SUCCESS:IMP-0216-probe1 never-converging predicate stops at the bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
