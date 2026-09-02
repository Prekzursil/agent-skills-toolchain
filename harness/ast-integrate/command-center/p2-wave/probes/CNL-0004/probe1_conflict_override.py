#!/usr/bin/env python3
"""Probe 1: conflict fixture records override_log; silent-win both-states.

Catalog tests_required[0]: owner vs auto disagreement must produce a recorded
override entry, not just a different roster.
Both-states: planted empty override_log FIRES; live composed result is SILENT.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import composer as C  # noqa: E402
import fixtures as F  # noqa: E402

OUT = HERE / "probe1-conflict.raw.json"


def main() -> int:
    invalid_errs = C.validate_instance(F.INVALID_CONSTRAINT, "owner_constraint")
    if not invalid_errs:
        print("FAILED:CNL-0004-probe1 invalid constraint produced 0 schema errors")
        return 1

    result = C.apply_owner_constraints(F.TASK_CONFLICT, F.CONSTRAINTS_CONFLICT)
    result_errs = C.validate_instance(result, "composition_result")
    if result_errs:
        print("FAILED:CNL-0004-probe1 composed result schema errors")
        print("\n".join(result_errs[:8]))
        return 1

    auto = result["auto_choice"]
    final = result["final_choice"]
    log = result["override_log"]
    ids = {e["constraint_id"] for e in log}

    if result["status"] != "COMPOSED" or final is None:
        print("FAILED:CNL-0004-probe1 expected COMPOSED conflict")
        print(json.dumps(result, indent=2)[:2000])
        return 1
    if C.choice_fingerprint(auto) == C.choice_fingerprint(final):
        print("FAILED:CNL-0004-probe1 auto and final are identical; not a conflict")
        return 1
    if not log:
        print("FAILED:CNL-0004-probe1 roster changed with empty override_log")
        return 1
    missing = {"OC-BUDGET", "OC-NOSRC", "OC-HUMAN"} - ids
    if missing:
        print(f"FAILED:CNL-0004-probe1 missing override ids {sorted(missing)}")
        return 1
    if any(e.get("visible") is not True for e in log):
        print("FAILED:CNL-0004-probe1 override entry not marked visible")
        return 1
    if "web-search" in final["source_classes"]:
        print("FAILED:CNL-0004-probe1 forbidden source survived")
        return 1
    if not any(s["kind"] == "human" and s["seat_id"] == "human.security" for s in final["roster"]):
        print("FAILED:CNL-0004-probe1 mandatory human missing")
        return 1
    if final["budget_usd"] > 40.0 + 1e-9:
        print(f"FAILED:CNL-0004-probe1 budget {final['budget_usd']} exceeds ceiling")
        return 1

    good_silent = C.silent_win(auto, final, log)
    planted = C.plant_silent_win(result)
    bad_fires = C.silent_win(
        planted["auto_choice"], planted["final_choice"], planted["override_log"]
    )
    if good_silent:
        print("FAILED:CNL-0004-probe1 live composed result is a silent-win")
        return 1
    if not bad_fires:
        print("FAILED:CNL-0004-probe1 planted empty override_log did not fire")
        return 1

    payload = {
        "probe": "probe1-conflict-override",
        "unit_id": "CNL-0004",
        "status": result["status"],
        "auto_budget_usd": auto["budget_usd"],
        "final_budget_usd": final["budget_usd"],
        "auto_source_classes": auto["source_classes"],
        "final_source_classes": final["source_classes"],
        "override_ids": sorted(ids),
        "override_count": len(log),
        "schema_errors_on_invalid": len(invalid_errs),
        "schema_errors_on_composed": 0,
        "silent_win_good": good_silent,
        "silent_win_planted": bad_fires,
        "negative_control": (
            "silent_win_check is SILENT on a COMPOSED conflict that carries "
            "override_log rows for every mutation; it FIRES on the planted "
            "twin with the same final roster and override_log=[]"
        ),
        "pass": True,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:CNL-0004-probe1 conflict records visible override_log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
