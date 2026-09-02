#!/usr/bin/env python3
"""Probe 1: every GENERATIVE record has an executable GENERATE/CRITIQUE schedule.

Counts schedules mechanically against the catalog-named family (n=7).
Does not read the design-note argument; it executes schedules.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402
import runtime as R  # noqa: E402
import schedules as S  # noqa: E402

NOTE = (
    C.REPO
    / "command-center/design/council/CNL-0042-executable-runtime-semantics-for-the-7-generative-protocol.md"
)


def main() -> int:
    cen = C.census()
    roster = C.roster_generative()
    verdicts = []
    fail = False
    for rec in roster:
        sched = S.good_schedule(rec)
        run = R.run_schedule(rec, sched)
        missing = []
        if run["silent"] is not True:
            missing.append("leak-on-good:" + ",".join(run.get("codes") if False else [f["code"] for f in run["findings"]]))
        if int(run["idea_count"]) < 2:
            missing.append("idea-count-too-low")
        if not run["frozen"]:
            missing.append("missing-GENERATE_CLOSED")
        if run["annotation_n"] < 1:
            missing.append("critique-did-not-run")
        executable = not missing
        row = {
            "record_id": rec["id"],
            "slug": rec["slug"],
            "verdict": "EXECUTABLE" if executable else "NOT-EXECUTABLE",
            "missing": missing,
            "idea_count": run["idea_count"],
            "rounds": [r["id"] for r in sched["rounds"]],
        }
        verdicts.append(row)
        if not executable:
            fail = True

    n = len(verdicts)
    ids = [v["record_id"] for v in verdicts]
    expected = list(C.NAMED_IDS)
    if n != C.EXPECTED_N or ids != expected:
        print(f"FAILED:CNL-0042-probe1 family count {n} ids={ids} expected={expected}")
        fail = True
    if not cen["counts_agree"]:
        print(f"FAILED:CNL-0042-probe1 census disagreement {json.dumps(cen, sort_keys=True)}")
        fail = True
    if any(d in ids for d in cen["decoy_ids"]):
        print("FAILED:CNL-0042-probe1 decoy FORECASTING record entered the family")
        fail = True

    if NOTE.is_file():
        note = json.loads(NOTE.read_text(encoding="utf-8"))
        if note.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:CNL-0042-probe1 note self-declared {note.get('state')}")
            fail = True
        blob = json.dumps(note)
        if "SUCCESS:CNL-0042" not in blob:
            print("FAILED:CNL-0042-probe1 sentinel missing from note")
            fail = True
        noted = [v.get("record_id") for v in (note.get("per_record") or [])]
        if noted and noted != ids:
            print(f"FAILED:CNL-0042-probe1 note per_record drift {noted} vs {ids}")
            fail = True

    payload = {
        "probe": "probe1-family-schedules",
        "unit_id": "CNL-0042",
        "family_n": n,
        "expected_n": C.EXPECTED_N,
        "library_present": bool(cen["library"]["present"]),
        "census_basis": "catalog-named-closed-set",
        "verdicts": verdicts,
        "pass": not fail and n == C.EXPECTED_N,
    }
    print(json.dumps(payload, sort_keys=True))
    if fail:
        print("FAILED:CNL-0042-probe1 executable schedules / family count")
        return 1
    print("SUCCESS:CNL-0042-probe1 7/7 executable GENERATE/CRITIQUE schedules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
