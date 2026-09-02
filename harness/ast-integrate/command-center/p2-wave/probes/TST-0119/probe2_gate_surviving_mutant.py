#!/usr/bin/env python3
"""Probe 2: independent reviewer — gate fails on a surviving predicate mutant.

Both-states:
  * live campaign (gated modules clean, helper survivor allowed) → gate PASS
  * helper-only survivor is NOT a gate failure (specificity)
  * live sentinel-deletion on the predicate, full suite → KILLED
  * same mutant, weakened suite → SURVIVES, and the gate FAILS
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from mutation.gate import evaluate_gate  # noqa: E402
from mutation.runner import plant_surviving_mutant, run_campaign  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "TST-0119.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0119-probe2 {msg}")
    return 1


def main() -> int:
    campaign = run_campaign(REPO)
    live_gate = evaluate_gate(campaign)
    if not live_gate["pass"]:
        return fail(f"live gated campaign must pass the gate: {live_gate}")

    helper_only = copy.deepcopy(campaign)
    for name in ("completion_predicate", "detector"):
        row = helper_only["per_module"][name]
        row["survivors"] = []
        row["survived"] = 0
        row["survival_score"] = 0.0
    helper_row = helper_only["per_module"]["helper_util"]
    if helper_row.get("survived", 0) < 1:
        return fail("helper_util must carry the recorded default-argument survivor")
    helper_gate = evaluate_gate(helper_only)
    if not helper_gate["pass"]:
        return fail("gate must ignore non-gated helper survivors")

    planted_record = copy.deepcopy(campaign)
    loc = "completion_predicate.py:sentinel-deletion"
    planted_record["per_module"]["completion_predicate"]["survivors"] = [
        {
            "operator": "sentinel-deletion",
            "location": loc,
            "module": "completion_predicate",
        }
    ]
    planted_record["per_module"]["completion_predicate"]["survived"] = 1
    planted_record["per_module"]["completion_predicate"]["survival_score"] = (
        1 / planted_record["per_module"]["completion_predicate"]["total"]
    )
    planted_gate = evaluate_gate(planted_record)
    if planted_gate["pass"]:
        return fail("gate silent on a surviving mutant in the predicate module")
    if not planted_gate["gated_survivors"]:
        return fail("gate did not name the predicate survivor")

    live_plant = plant_surviving_mutant(REPO)
    if not live_plant["full_suite_killed"]:
        return fail("full predicate suite did not kill sentinel-deletion")
    if not live_plant["weak_suite_survived"]:
        return fail("weakened suite did not let sentinel-deletion survive")

    weak_campaign = {
        "per_module": {
            "completion_predicate": {
                "survivors": [
                    {
                        "operator": live_plant["operator"],
                        "location": live_plant["location"],
                    }
                ]
            },
            "detector": {"survivors": []},
        }
    }
    weak_gate = evaluate_gate(weak_campaign)
    if weak_gate["pass"]:
        return fail("gate passed a live weakened-suite survivor in the predicate")

    if RECEIPT.is_file():
        rec = json.loads(RECEIPT.read_text(encoding="utf-8"))
        tests = {t.get("id"): t for t in (rec.get("tests") or []) if isinstance(t, dict)}
        wanted = "test_gate_fails_on_a_surviving_mutant_in_the_predicate_module"
        if wanted not in tests or tests[wanted].get("result") != "PASS":
            return fail(f"receipt missing PASS {wanted}")

    payload = {
        "pass": True,
        "probe": "probe2-gate-surviving-mutant",
        "unit_id": "TST-0119",
        "live_gate_pass": True,
        "helper_survivor_does_not_fail_gate": True,
        "record_planted_predicate_fails_gate": True,
        "full_suite_killed_sentinel_deletion": True,
        "weak_suite_survived_sentinel_deletion": True,
        "live_weak_gate_fail": True,
        "gated_survivors": planted_gate["gated_survivors"],
        "plant": {
            "operator": live_plant["operator"],
            "location": live_plant["location"],
            "full_suite_exit_code": live_plant["full_suite_exit_code"],
            "weak_suite_exit_code": live_plant["weak_suite_exit_code"],
        },
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        "live_gate=PASS helper_ignored=True planted_predicate=FAIL "
        f"full_killed={live_plant['full_suite_killed']} "
        f"weak_survived={live_plant['weak_suite_survived']}"
    )
    print("SUCCESS:TST-0119-probe2 gate fails on surviving predicate mutant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
