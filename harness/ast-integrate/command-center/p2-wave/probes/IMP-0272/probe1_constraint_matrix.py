#!/usr/bin/env python3
"""Probe 1: feasible/infeasible constraint matrix for diversity.solve."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MOD_PATH = REPO / "tools/council/participants/diversity.py"


def load_mod():
    spec = importlib.util.spec_from_file_location("imp0272_diversity", MOD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {MOD_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0272-probe1 {msg}")
    return 1


def main() -> int:
    if not MOD_PATH.is_file():
        return fail(f"missing {MOD_PATH.relative_to(REPO).as_posix()}")
    d = load_mod()
    rows = d.run_matrix()
    feasible = [r for r in rows if r["artifact"]["feasible"]]
    infeasible = [r for r in rows if not r["artifact"]["feasible"]]
    failed = [r["id"] for r in rows if not r["passed"]]
    if failed:
        return fail(f"matrix failures {failed}")
    if len(feasible) < 3 or len(infeasible) < 3:
        return fail(f"matrix too thin feasible={len(feasible)} infeasible={len(infeasible)}")
    for r in infeasible:
        art = r["artifact"]
        if art["waiver"] is None:
            return fail(f"{r['id']} infeasible without waiver")
        if art["independence_assumption"] != d.VOID:
            return fail(f"{r['id']} did not void independence")
        ok, why = d.check_artifact(art)
        if not ok:
            return fail(f"{r['id']} check {why}")
    for r in feasible:
        art = r["artifact"]
        if art["waiver"] is not None:
            return fail(f"{r['id']} feasible with stray waiver")
        if art["independence_assumption"] != d.INTACT:
            return fail(f"{r['id']} feasible but independence not intact")
        if not art["council_ran"]:
            return fail(f"{r['id']} feasible but council did not run")
    one_vendor = next(r for r in rows if r["id"] == "I1-one-vendor-reachable")
    if not one_vendor["council_ran"]:
        return fail("single-vendor reachable pool did not run the council")
    if one_vendor["independence_assumption"] != "void":
        return fail("single-vendor run did not report independence void")
    same_vendor = next(r for r in rows if r["id"] == "I2-same-vendor-twice-not-vendor-diverse")
    if same_vendor["artifact"]["vendor_diverse"]:
        return fail("same-vendor twice counted as vendor-diverse")
    payload = {
        "pass": True,
        "probe": "probe1-constraint-matrix",
        "unit_id": "IMP-0272",
        "feasible_cases": [r["id"] for r in feasible],
        "infeasible_cases": [r["id"] for r in infeasible],
        "one_vendor_council_ran": True,
        "one_vendor_independence": one_vendor["independence_assumption"],
        "same_vendor_twice_vendor_diverse": False,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"matrix feasible={len(feasible)} infeasible={len(infeasible)} "
        f"one_vendor_ran={one_vendor['council_ran']} "
        f"one_vendor_assumption={one_vendor['independence_assumption']}"
    )
    print("SUCCESS:IMP-0272-probe1 feasible/infeasible constraint matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
