#!/usr/bin/env python3
"""Probe 1: ramp until guard trips before degrade; abort cleans up; lower-ceiling reviewer."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import jsonschema  # noqa: E402
import ramp as R  # noqa: E402

ART = REPO / "command-center" / "receipts" / "BLD-0057.json"
SCHEMA = REPO / "command-center" / "schema" / "scale-model.schema.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:BLD-0057-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "BLD-0057":
        print("FAILED:BLD-0057-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:BLD-0057-probe1 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:BLD-0057" not in text:
        print("FAILED:BLD-0057-probe1 sentinel absent")
        return 1
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        print("FAILED:BLD-0057-probe1 schema", errs[0].message)
        return 1

    trip = R.run_guard_trip(max_tagged=6, degrade_at=16)
    review = R.run_guard_trip(max_tagged=4, degrade_at=14)
    abort = R.run_abort_midway(abort_after=3)
    if not trip.get("guard_before_degrade"):
        print("FAILED:BLD-0057-probe1 guard did not trip before degrade", trip)
        return 1
    if trip.get("trip_action") != "REFUSE_RAISE":
        print("FAILED:BLD-0057-probe1 action not REFUSE_RAISE", trip.get("trip_action"))
        return 1
    if not review.get("guard_before_degrade"):
        print("FAILED:BLD-0057-probe1 reviewer ramp failed", review)
        return 1
    if int(review.get("max_tagged") or 0) >= int(trip.get("max_tagged") or 0):
        print("FAILED:BLD-0057-probe1 reviewer ceiling not lower")
        return 1
    if not abort.get("cleanup_clean") or not abort.get("process_count_restored"):
        print("FAILED:BLD-0057-probe1 abort left orphans", abort)
        return 1
    if trip.get("orphans_after") or review.get("orphans_after"):
        print("FAILED:BLD-0057-probe1 orphans after ramp")
        return 1

    art_trip = (doc.get("guard") or {}).get("trip") or {}
    if int(art_trip.get("degrade_at") or 0) != 16:
        print("FAILED:BLD-0057-probe1 artifact degrade_at mismatch")
        return 1
    if not doc.get("reviewer", {}).get("repeated_ramp_at_lower_ceiling"):
        print("FAILED:BLD-0057-probe1 reviewer flag missing")
        return 1
    print(
        json.dumps(
            {
                "tripped": trip["tripped"],
                "tagged_at_trip": trip["tagged_at_trip"],
                "reviewer_tagged_at_trip": review["tagged_at_trip"],
                "abort_clean": abort["cleanup_clean"],
                "guard_before_degrade": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:BLD-0057-probe1 ramp guard-before-degrade abort-clean reviewer-replay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
