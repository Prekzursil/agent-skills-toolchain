#!/usr/bin/env python3
"""Probe 2: condition-8 both-states + planted disagreement reported by the differ."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from clean_room import evaluate  # noqa: E402
from differ import differ  # noqa: E402
from observe import ensure_fixtures, synthetic_cases  # noqa: E402
from shipped_adapter import evaluate_observation as shipped_eval  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:CNF-0170-probe2 {msg}")
    return 1


def _cond(result: dict, n: int) -> dict:
    for row in result.get("conditions") or []:
        if int(row["n"]) == n:
            return row
    return {}


def main() -> int:
    ensure_fixtures()
    cases = {c["id"]: c for c in synthetic_cases()}
    good = cases["FIX-HEALTHY"]
    bad = cases["FIX-C8-control-miss"]

    cr_good = evaluate(good)
    cr_bad = evaluate(bad)
    sh_good = shipped_eval(good)
    sh_bad = shipped_eval(bad)

    if _cond(cr_good, 8).get("outcome") != "SATISFIED":
        print(json.dumps(_cond(cr_good, 8), indent=2))
        return _fail("clean-room C8 did not SATISFY the healthy both-states control")
    if _cond(cr_bad, 8).get("outcome") != "UNSATISFIED":
        print(json.dumps(_cond(cr_bad, 8), indent=2))
        return _fail("clean-room C8 did not fail the broken negative-control receipt")
    if _cond(sh_bad, 8).get("outcome") == "SATISFIED":
        print(json.dumps(_cond(sh_bad, 8), indent=2))
        return _fail("shipped C8 SATISFIED a receipt that must fail condition 8")

    planted = evaluate(bad, invert={8})
    if _cond(planted, 8).get("outcome") != "SATISFIED":
        return _fail("planted invert did not flip C8 on the broken receipt")
    plant_diff = differ(cr_bad, planted)
    c8_reported = any(int(d["n"]) == 8 for d in plant_diff["disagreements"])
    if not c8_reported or plant_diff["disagreement_count"] < 1:
        print(json.dumps(plant_diff, indent=2)[:4000])
        return _fail("differ did not report the planted C8 disagreement")

    vs_shipped = differ(cr_bad, sh_bad)
    summary = {
        "probe": "probe2-planted-c8",
        "c8_clean_room_good": _cond(cr_good, 8),
        "c8_clean_room_bad": _cond(cr_bad, 8),
        "c8_shipped_good": _cond(sh_good, 8),
        "c8_shipped_bad": _cond(sh_bad, 8),
        "shipped_discriminates_c8": (
            _cond(sh_good, 8).get("outcome") == "SATISFIED"
            and _cond(sh_bad, 8).get("outcome") == "UNSATISFIED"
        ),
        "planted_disagreements": plant_diff["disagreements"],
        "clean_vs_shipped_on_bad_c8": vs_shipped["disagreements"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(
        "c8_good="
        + str(_cond(cr_good, 8).get("outcome"))
        + " c8_bad="
        + str(_cond(cr_bad, 8).get("outcome"))
        + " planted_reported="
        + str(c8_reported)
        + " shipped_discriminates="
        + str(summary["shipped_discriminates_c8"])
    )
    print("SUCCESS:CNF-0170-probe2 condition-8 both-states and planted differ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
