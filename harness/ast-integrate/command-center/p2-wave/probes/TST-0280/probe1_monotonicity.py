#!/usr/bin/env python3
"""Probe 1: monotonicity (and claimed axioms) on >=10k generated profiles per method."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.vote.axiom_tests import (  # noqa: E402
    METHOD_IDS,
    N_PROFILES,
    evaluate_all,
)

UNIT = "TST-0280"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    report = evaluate_all(n=N_PROFILES, mutant=False)
    rows = []
    for method in report["methods"]:
        mono = method["axioms"]["monotonicity"]
        if int(mono.get("n_profiles") or 0) < N_PROFILES:
            return fail(f"{method['method']} monotonicity n_profiles<{N_PROFILES}")
        if method["claimed_fail"]:
            return fail(f"{method['method']} claimed axiom FAIL {mono}")
        if not method["exception_ok"]:
            return fail(f"{method['method']} EXCEPTION axiom unseen")
        if not method["pass"]:
            return fail(f"{method['method']} overall fail")
        rows.append(
            {
                "method": method["method"],
                "monotonicity_status": mono["status"],
                "n_profiles": mono.get("n_profiles"),
                "n_applicable": mono.get("n_applicable"),
                "n_violations": mono.get("n_violations"),
                "wilson": mono.get("wilson"),
                "claim": mono.get("claim"),
            }
        )
    irv = report["irv_exception"]
    if not irv.get("demonstrated_nonmonotonicity"):
        return fail("IRV planted non-monotonicity not demonstrated")
    ranked = next(m for m in report["methods"] if m["method"] == "ranked-choice")
    if ranked["axioms"]["monotonicity"]["status"] != "EXCEPTION-DEMONSTRATED":
        return fail("ranked-choice monotonicity was not recorded as EXCEPTION")
    if not report["cycle"]["pass"]:
        return fail("cycle fixture missing from evaluate_all")
    if report["n_methods_pass"] != len(METHOD_IDS):
        return fail(f"n_methods_pass={report['n_methods_pass']}")

    payload = {
        "probe": "probe1-monotonicity",
        "unit_id": UNIT,
        "pass": True,
        "n_profiles": N_PROFILES,
        "n_methods": report["n_methods"],
        "n_methods_pass": report["n_methods_pass"],
        "suite_red": report["suite_red"],
        "methods": rows,
        "irv_before_winner": irv["before"]["winner"],
        "irv_after_raise_A_winner": irv["after_raise_A"]["winner"],
        "bits_sha256": {
            m["method"]: m["axioms"]["monotonicity"].get("bits_sha256")
            for m in report["methods"]
        },
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"n_profiles={N_PROFILES} methods_pass={report['n_methods_pass']}/{len(METHOD_IDS)} "
        f"irv={irv['before']['winner']}->{irv['after_raise_A']['winner']}"
    )
    print(f"SUCCESS:{UNIT}-probe1 monotonicity >=10k profiles per method")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
