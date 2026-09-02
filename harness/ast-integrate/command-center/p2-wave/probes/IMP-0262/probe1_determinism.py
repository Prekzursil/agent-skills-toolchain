#!/usr/bin/env python3
"""Probe 1: compile determinism over 20 specs, plus plan-vs-trace.

For each of 20 fixtures:
  * two compiles of the identical object are byte-identical
  * two compiles of key-order-shuffled equivalent objects are byte-identical
  * the plan names every participant, round, and gate it will execute
  * a dry-run trace of the compiled plan matches named turns and gates
No model calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.compile import (  # noqa: E402
    CompileError,
    compile_spec,
    digest_plan,
    dumps_plan,
    execute_plan,
    plan_vs_trace,
)

from fixtures import spec_pair, twenty_specs  # noqa: E402

UNIT = "IMP-0262"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def names_complete(spec: dict, plan: dict) -> list[str]:
    errors: list[str] = []
    want_seats = sorted(str(s["id"]) for s in spec["participants"])
    got_seats = list(plan.get("named_participants") or [])
    if sorted(got_seats) != want_seats:
        errors.append(f"participants named={got_seats} want={want_seats}")
    if got_seats != sorted(got_seats):
        errors.append("named_participants is not sorted by id")
    if not plan.get("named_rounds"):
        errors.append("named_rounds empty")
    if not plan.get("named_turns"):
        errors.append("named_turns empty")
    if not plan.get("named_gates"):
        errors.append("named_gates empty")
    plan_round_ids = [r["round_id"] for r in plan.get("rounds") or []]
    if plan_round_ids != list(plan.get("named_rounds") or []):
        errors.append("named_rounds does not match rounds[].round_id")
    nested_turns = [t["turn_id"] for r in plan.get("rounds") or [] for t in r["turns"]]
    if nested_turns != list(plan.get("named_turns") or []):
        errors.append("named_turns does not match nested turn_ids")
    nested_gates = [g["gate_id"] for r in plan.get("rounds") or [] for g in r["gates"]]
    nested_gates += [g["gate_id"] for g in plan.get("final_gates") or []]
    if nested_gates != list(plan.get("named_gates") or []):
        errors.append("named_gates does not match nested gate_ids")
    unnamed = []
    for rnd in plan.get("rounds") or []:
        if not rnd.get("round_id"):
            unnamed.append("round")
        for turn in rnd.get("turns") or []:
            if not turn.get("turn_id") or not turn.get("participant_id"):
                unnamed.append(str(turn))
        for gate in rnd.get("gates") or []:
            if not gate.get("gate_id") or not gate.get("kind"):
                unnamed.append(str(gate))
    if unnamed:
        errors.append(f"unnamed entities: {unnamed[:4]}")
    if plan.get("model_calls_scheduled") != 0:
        errors.append("model_calls_scheduled != 0")
    if plan.get("compiled_before_model_call") is not True:
        errors.append("compiled_before_model_call is not True")
    return errors


def main() -> int:
    specs = twenty_specs()
    if len(specs) != 20:
        return fail(f"fixture count {len(specs)} want=20")
    rows = []
    all_equal = True
    all_named = True
    all_trace = True
    for n, spec in enumerate(specs):
        a, b = spec_pair(n)
        try:
            p1 = compile_spec(spec)
            p2 = compile_spec(spec)
            p_a = compile_spec(a)
            p_b = compile_spec(b)
        except CompileError as exc:
            return fail(f"spec {n} compile error: {exc}")
        d1, d2, da, db = (
            digest_plan(p1),
            digest_plan(p2),
            digest_plan(p_a),
            digest_plan(p_b),
        )
        same_object = d1 == d2
        same_key_order = da == db == d1
        named_errs = names_complete(spec, p1)
        trace = execute_plan(p1)
        diff = plan_vs_trace(p1, trace)
        trace_ok = (
            diff["turns_equal"]
            and diff["gates_equal"]
            and diff["model_calls"] == 0
            and not diff["missing_turns"]
            and not diff["extra_turns"]
            and not diff["missing_gates"]
            and not diff["extra_gates"]
        )
        if not same_object or not same_key_order:
            all_equal = False
        if named_errs:
            all_named = False
        if not trace_ok:
            all_trace = False
        rows.append(
            {
                "n": n,
                "digest": d1,
                "bytes": len(dumps_plan(p1)),
                "same_object": same_object,
                "same_shuffled_keys": same_key_order,
                "named_ok": not named_errs,
                "named_errors": named_errs,
                "n_participants": len(p1["named_participants"]),
                "n_rounds": len(p1["named_rounds"]),
                "n_turns": len(p1["named_turns"]),
                "n_gates": len(p1["named_gates"]),
                "trace_ok": trace_ok,
                "trace_model_calls": trace.get("model_calls"),
            }
        )
        if not same_object or not same_key_order or named_errs or not trace_ok:
            return fail(
                f"spec {n} same_object={same_object} shuffled={same_key_order} "
                f"named={named_errs} trace={diff}"
            )

    plan0 = compile_spec(specs[0])
    trace0 = execute_plan(plan0)
    diff0 = plan_vs_trace(plan0, trace0)

    payload = {
        "probe": "probe1-determinism",
        "unit_id": UNIT,
        "n_specs": len(rows),
        "all_byte_identical": all_equal,
        "all_participants_rounds_gates_named": all_named,
        "all_plan_vs_trace_match": all_trace,
        "digests": [r["digest"] for r in rows],
        "rows": rows,
        "plan_vs_trace_fixture0": diff0,
        "plan0_named_participants": plan0["named_participants"],
        "plan0_named_rounds": plan0["named_rounds"],
        "plan0_named_gates": plan0["named_gates"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
    print(
        f"n=20 identical={all_equal} named={all_named} "
        f"plan_vs_trace={all_trace} model_calls=0"
    )
    print("SUCCESS:IMP-0262-probe1 compile determinism over 20 specs; plan-vs-trace match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
