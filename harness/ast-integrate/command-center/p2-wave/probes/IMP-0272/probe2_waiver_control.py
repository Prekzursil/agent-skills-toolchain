#!/usr/bin/env python3
"""Probe 2: suppress waiver emission and assert the artifact check FAILS."""
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
    print(f"FAILED:IMP-0272-probe2 {msg}")
    return 1


ONE_VENDOR_POOL = [
    {"id": "a1", "vendor": "anthropic", "model": "opus", "reachable": True},
    {"id": "a2", "vendor": "anthropic", "model": "sonnet", "reachable": True},
    {"id": "o1", "vendor": "openai", "model": "gpt-5", "reachable": False},
]
CONSTRAINT = {"min_vendors": 2, "min_models": 2, "seat_count": 2}


def main() -> int:
    d = load_mod()
    honest = d.solve(ONE_VENDOR_POOL, CONSTRAINT, emit_waiver=True)
    ok, why = d.check_artifact(honest)
    if not ok:
        return fail(f"honest infeasible seating failed check: {why}")
    if honest.waiver is None:
        return fail("honest seating omitted waiver")
    if honest.independence_assumption != d.VOID:
        return fail("honest seating did not void independence")
    if not honest.council_ran:
        return fail("honest single-vendor seating refused to run")

    silenced = d.solve(ONE_VENDOR_POOL, CONSTRAINT, emit_waiver=False)
    ok_bad, why_bad = d.check_artifact(silenced)
    if ok_bad:
        return fail("suppressed-waiver seating passed the artifact check")
    if why_bad != "diversity_shortfall_without_waiver":
        return fail(f"unexpected fail reason {why_bad!r}")
    if silenced.waiver is not None:
        return fail("emit_waiver=False still attached a waiver")
    if silenced.council_ran is not True:
        return fail("suppressed-waiver path must still run the council")

    stripped = d.without_waiver(honest)
    ok_strip, why_strip = d.check_artifact(stripped)
    if ok_strip:
        return fail("post-hoc waiver strip passed the artifact check")
    if why_strip != "diversity_shortfall_without_waiver":
        return fail(f"strip fail reason {why_strip!r}")

    feasible = d.solve(
        [
            {"id": "a1", "vendor": "anthropic", "model": "opus", "reachable": True},
            {"id": "o1", "vendor": "openai", "model": "gpt-5", "reachable": True},
        ],
        {"min_vendors": 2, "min_models": 2, "seat_count": 2},
        emit_waiver=True,
    )
    ok_f, why_f = d.check_artifact(feasible)
    if not ok_f or not feasible.feasible:
        return fail(f"feasible control failed {why_f}")
    if feasible.waiver is not None:
        return fail("feasible seating emitted a waiver")

    payload = {
        "pass": True,
        "probe": "probe2-waiver-negative-control",
        "unit_id": "IMP-0272",
        "honest_check": why,
        "suppressed_check_failed": True,
        "suppressed_reason": why_bad,
        "stripped_reason": why_strip,
        "council_ran_with_void_independence": True,
        "feasible_control": why_f,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"honest_ok={ok} suppressed_ok={ok_bad} suppressed_reason={why_bad} "
        f"strip_ok={ok_strip} council_ran={honest.council_ran} "
        f"independence={honest.independence_assumption}"
    )
    print("SUCCESS:IMP-0272-probe2 waiver emission negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
