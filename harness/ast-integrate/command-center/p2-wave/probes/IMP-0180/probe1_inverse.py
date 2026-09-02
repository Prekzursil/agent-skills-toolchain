#!/usr/bin/env python3
"""Probe 1: eight separate inverse assertions, not one generic claim.

For each fusion strategy: JSON-round-trip decompose(fuse(a,b)) recovers
{fingerprint(a), fingerprint(b)}. Also guards: distinct sources, rename
invariance, gate-mutation sensitivity, no sidecar sources, splice plan
differs from both parents.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fusion import (  # noqa: E402
    STRATEGIES,
    fuse,
    fused_plan_stages,
    inverse_holds,
    mutate_gate,
    rename_workflow,
    source_a,
    source_b,
    structural_fingerprint,
    workflow,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0180-probe1 {msg}")
    return 1


def main() -> int:
    if len(STRATEGIES) != 8:
        return fail(f"strategy_count={len(STRATEGIES)} want=8")
    if len(set(STRATEGIES)) != 8:
        return fail("duplicate strategy names")

    a = source_a()
    b = source_b()
    fp_a = structural_fingerprint(a)
    fp_b = structural_fingerprint(b)
    if fp_a == fp_b:
        return fail("source fingerprints collide; inverse set-equality would be vacuous")

    renamed = rename_workflow(a, "renamed-")
    if structural_fingerprint(renamed) != fp_a:
        return fail("fingerprint not rename-invariant")
    if structural_fingerprint(mutate_gate(a)) == fp_a:
        return fail("fingerprint silent on gate mutation")

    rows = []
    for strategy in STRATEGIES:
        fused = fuse(strategy, a, b)
        if "sources" in fused:
            return fail(f"{strategy} emitted sidecar sources")
        if set(fused.keys()) != {"strategy", "encoding"}:
            return fail(f"{strategy} unexpected keys {sorted(fused.keys())}")
        if fused["strategy"] != strategy:
            return fail(f"{strategy} encoding mislabelled {fused['strategy']}")

        result = inverse_holds(strategy, a, b, fused)
        print(
            "ASSERT "
            f"{strategy} inverse={'PASS' if result['ok'] else 'FAIL'} "
            f"want={result['want'][0][:12]}..,{result['want'][1][:12]}.. "
            f"got_n={len(result['got'])} err={result['error']}"
        )
        if not result["ok"]:
            print(json.dumps(result, indent=2)[:2000])
            return fail(f"{strategy} inverse failed")
        rows.append(result)

        plan = fused_plan_stages(fused)
        if not plan:
            return fail(f"{strategy} empty fused plan")
        plan_fp = structural_fingerprint(workflow(f"plan.{strategy}", plan))
        if plan_fp == fp_a or plan_fp == fp_b:
            return fail(f"{strategy} fused plan is a silent parent (no-op fusion)")

    if len(rows) != 8:
        return fail(f"assertion_count={len(rows)} want=8")
    passed = [r["strategy"] for r in rows if r["ok"]]
    if passed != list(STRATEGIES):
        return fail(f"passed={passed}")

    payload = {
        "probe": "probe1-inverse",
        "unit_id": "IMP-0180",
        "pass": True,
        "assertions": 8,
        "strategies": list(STRATEGIES),
        "fp_a": fp_a,
        "fp_b": fp_b,
        "rename_invariant": True,
        "gate_mutation_changes_fp": True,
        "computed_not_generic": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:IMP-0180-probe1 8/8 fusion strategies satisfy decompose(fuse(a,b)) == {a,b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
