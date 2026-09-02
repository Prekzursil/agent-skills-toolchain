#!/usr/bin/env python3
"""Probe 1: independent family recount + executable schedule (or NOT-EXECUTABLE) per record.

Mechanism A (this probe): regex-extract P-ids from CNL-0041.question_or_target.
Library file 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is searched and must not be invented.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import family as F  # noqa: E402
import runtime as R  # noqa: E402

OUT = HERE / "probe1-family-schedules.raw.json"


def main() -> int:
    lib = F.library_hits()
    unit = F.catalog_unit()
    named = F.catalog_named_members(unit)
    roster = F.roster_members()
    expected_ids = [m["id"] for m in named]
    good = F.family_count_check(roster, expected_ids)
    bad_doc = json.loads((HERE / "fixtures" / "family_roster_bad.json").read_text(encoding="utf-8"))
    bad = F.family_count_check(F.roster_members(bad_doc), expected_ids)

    knobs = json.loads((HERE / "fixtures" / "known_good_knobs.json").read_text(encoding="utf-8"))
    protocols = R.load_protocols()
    runs = []
    for proto in protocols:
        run = R.run_protocol(proto, knobs=knobs)
        runs.append(
            {
                "id": run["id"],
                "slug": run.get("slug"),
                "verdict": run["verdict"],
                "missing_element": run.get("missing_element"),
                "anonymity_lift_event": run.get("anonymity_lift_event"),
                "lift_index": run.get("lift_index"),
                "stopping": run.get("stopping"),
                "event_types": [e["type"] for e in run.get("events") or []],
            }
        )

    mutant = deepcopy(protocols[0])
    mutant["schedule"] = [s for s in mutant["schedule"] if s != "UNSEAL"]
    mutant_run = R.run_protocol(mutant, knobs=knobs)

    live_ids = [p["id"] for p in protocols]
    fail = False
    reasons: list[str] = []
    if lib:
        fail = True
        reasons.append(f"library unexpectedly present: {lib}")
    if len(named) != F.EXPECTED_N:
        fail = True
        reasons.append(f"catalog named count {len(named)} != {F.EXPECTED_N}")
    if expected_ids != ["P20", "P21", "P22", "P23", "P24", "P25"]:
        fail = True
        reasons.append(f"catalog ids {expected_ids}")
    if not good["silent"]:
        fail = True
        reasons.append(f"good roster fired {good}")
    if not bad["fired"]:
        fail = True
        reasons.append("bad roster (P07 mis-assignment) did not fire")
    if live_ids != expected_ids:
        fail = True
        reasons.append(f"protocols.json ids {live_ids} != catalog {expected_ids}")
    if len(runs) != F.EXPECTED_N:
        fail = True
        reasons.append(f"run count {len(runs)}")
    for row in runs:
        if row["verdict"] != "EXECUTABLE":
            fail = True
            reasons.append(f"{row['id']} not EXECUTABLE")
        if row.get("anonymity_lift_event") != "UNSEAL":
            fail = True
            reasons.append(f"{row['id']} lift != UNSEAL")
        if "UNSEAL" not in (row.get("event_types") or []):
            fail = True
            reasons.append(f"{row['id']} schedule missing UNSEAL event")
        if not (row.get("stopping") or {}).get("satisfied"):
            fail = True
            reasons.append(f"{row['id']} stopping not satisfied")
    if mutant_run.get("verdict") != "NOT-EXECUTABLE":
        fail = True
        reasons.append("UNSEAL-stripped mutant was not NOT-EXECUTABLE")
    missing = str(mutant_run.get("missing_element") or "")
    if "UNSEAL" not in missing:
        fail = True
        reasons.append(f"mutant missing_element did not name UNSEAL: {missing}")

    doc = {
        "library_hits": lib,
        "library_present": bool(lib),
        "catalog_named": named,
        "catalog_named_n": len(named),
        "roster_ids": [m["id"] for m in roster],
        "good_roster_silent": good["silent"],
        "bad_roster_fired": bad["fired"],
        "bad_roster_reasons": bad["reasons"],
        "runs": runs,
        "mutant_not_executable": mutant_run.get("verdict"),
        "mutant_missing_element": mutant_run.get("missing_element"),
        "pass": not fail,
        "reasons": reasons,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"library_present={bool(lib)} catalog_n={len(named)} "
        f"roster_silent={good['silent']} bad_fired={bad['fired']} "
        f"executable={sum(1 for r in runs if r['verdict']=='EXECUTABLE')}/{len(runs)} "
        f"mutant={mutant_run.get('verdict')}"
    )
    if fail:
        print("FAILED:CNL-0041-probe1 " + "; ".join(reasons))
        return 1
    print("SUCCESS:CNL-0041-probe1 family recount and executable schedules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
