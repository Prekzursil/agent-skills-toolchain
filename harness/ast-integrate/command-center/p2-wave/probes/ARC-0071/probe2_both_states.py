#!/usr/bin/env python3
"""Probe 2: both-states control — delete one dissent, the check fires.

Intact report: scorecard_ids - report_ids is empty.
Mutant report (one recorded dissent removed): the missing set contains
that victim id. Distortion of the dissenting reviewer's reasoning fails
the field-for-field check. Independent of the artifact's boolean flags.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

ART = REPO / "command-center/phase3/MINORITY-REPORT.json"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0071-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("MINORITY-REPORT.json missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:ARC-0071" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")

    resolved = E.resolve_inputs(REPO)
    sc_rows = E.extract_dissents(resolved["scorecards"])
    rp_rows = E.extract_report_positions(doc)
    states = E.both_states(sc_rows, rp_rows, resolved["scorecards_path"])
    if not states["discriminates"]:
        return fail(f"both-states did not discriminate {states}")
    if not states["silent_on_clean"]:
        return fail("intact report not silent")
    if not states["fires_on_delete"]:
        return fail("deleted dissent did not appear in missing set")

    pub = doc.get("both_states") or {}
    if pub.get("victim_id") != states["victim_id"]:
        return fail("artifact victim_id != live both-states victim")
    if pub.get("discriminates") is not True:
        return fail("artifact both_states.discriminates is not true")

    judge = resolved["reviewer_judge_id"]
    clean = E.undistorted(sc_rows, rp_rows, judge)
    if not clean["undistorted"]:
        return fail("clean reviewer check failed")
    rev_ids = [r["dissent_id"] for r in sc_rows if r["judge_id"] == judge]
    if not rev_ids:
        return fail("reviewer has no recorded dissent")
    dirty = E.undistorted(
        sc_rows, E.distort_reasoning(rp_rows, rev_ids[0]), judge
    )
    if dirty["undistorted"]:
        return fail("distorted reasoning still counted undistorted")
    if not dirty["field_mismatches"]:
        return fail("distortion mutant produced no field mismatch")

    print(
        json.dumps(
            {
                "victim_id": states["victim_id"],
                "silent_on_clean": states["silent_on_clean"],
                "fires_on_delete": states["fires_on_delete"],
                "discriminates": states["discriminates"],
                "mutant_missing": states["mutant_missing"],
                "distortion_fired": True,
                "reviewer_judge_id": judge,
            },
            sort_keys=True,
        )
    )
    print(
        f"victim={states['victim_id']} "
        f"clean={states['silent_on_clean']} "
        f"fires={states['fires_on_delete']}"
    )
    print("SUCCESS:ARC-0071-probe2 both-states delete-one and distortion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
