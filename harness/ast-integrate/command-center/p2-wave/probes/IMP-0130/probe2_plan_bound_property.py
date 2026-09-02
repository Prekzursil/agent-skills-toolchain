#!/usr/bin/env python3
"""Probe 2: property test — executor plan length never exceeds max_iterations.

200 randomly generated Loop bodies, each with a positive max_iterations.
A never-converging convergence_expr is used so the bound, not the predicate,
is what stops the static plan. Plan length is counted from plan_loop output,
not from prose.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.plan import plan_length, plan_loop  # noqa: E402
from agentspec.spec import Loop  # noqa: E402
from agentspec.validate import validate_workflow  # noqa: E402

N_SAMPLES = 200
SEED = 130
NEVER_CONVERGE = "False"


def _body(rng: random.Random, n: int) -> tuple[str, ...]:
    return tuple(f"u{i:02d}" for i in range(n))


def main() -> int:
    rng = random.Random(SEED)
    samples: list[dict] = []
    failures: list[dict] = []
    for i in range(N_SAMPLES):
        body_len = rng.randint(1, 12)
        cap = rng.randint(1, 40)
        body = _body(rng, body_len)
        loop = Loop(
            id=f"loop-{i:03d}",
            body=body,
            convergence_expr=NEVER_CONVERGE,
            max_iterations=cap,
            on_bound_reached=rng.choice(["abort", "fail", "return_last"]),
        )
        workflow = {
            "id": f"wf-{i:03d}",
            "spec_version": "1.0.0",
            "units": [{"id": u} for u in body],
            "nodes": [
                {
                    "type": "Loop",
                    "id": loop.id,
                    "body": list(body),
                    "convergence_expr": NEVER_CONVERGE,
                    "max_iterations": cap,
                    "on_bound_reached": loop.on_bound_reached,
                }
            ],
        }
        viol = validate_workflow(workflow)
        plan = plan_loop(loop)
        length = plan_length(loop)
        row = {
            "i": i,
            "body_len": body_len,
            "max_iterations": cap,
            "plan_length": length,
            "within_bound": length <= cap,
            "validate_ok": viol == [],
        }
        samples.append(row)
        if length > cap or viol or length != len(plan):
            failures.append(row)

    # Explicit never-converge + tiny cap + large body.
    huge = Loop(
        id="never-converge-huge-body",
        body=_body(rng, 64),
        convergence_expr=NEVER_CONVERGE,
        max_iterations=5,
        on_bound_reached="abort",
    )
    huge_len = plan_length(huge)
    huge_ok = huge_len <= 5 == huge.max_iterations and huge_len == 5

    n_ok = sum(1 for s in samples if s["within_bound"] and s["validate_ok"])
    result = {
        "probe": "probe2-plan-bound-property",
        "unit_id": "IMP-0130",
        "n_samples": N_SAMPLES,
        "seed": SEED,
        "n_within_bound": n_ok,
        "n_failures": len(failures),
        "max_observed_plan_length": max(s["plan_length"] for s in samples),
        "max_requested_iterations": max(s["max_iterations"] for s in samples),
        "never_converge_huge_body_plan_length": huge_len,
        "never_converge_huge_body_ok": huge_ok,
        "pass": False,
    }
    ok = n_ok == N_SAMPLES and not failures and huge_ok
    result["pass"] = ok
    print(json.dumps(result, indent=2, sort_keys=True))
    print(
        f"samples={N_SAMPLES} within_bound={n_ok} failures={len(failures)} "
        f"huge_plan_len={huge_len} huge_ok={huge_ok}"
    )
    if not ok:
        if failures:
            print(f"first_failure={json.dumps(failures[0])}")
        print("FAILED:IMP-0130-probe2 plan length exceeded max_iterations")
        return 1
    print(
        "SUCCESS:IMP-0130-probe2 plan length <= max_iterations for "
        f"{N_SAMPLES} generated bodies"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
