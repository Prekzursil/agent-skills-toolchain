#!/usr/bin/env python3
"""Probe 2: direction-split disagreement matrix + CNF-0140 census re-injection."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

ART = REPO / "command-center" / "receipts" / "CNF-0142.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0142-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0142" not in json.dumps(doc):
        return fail("sentinel absent")

    try:
        E.validate_matrix({"accuracy": 0.86})
        return fail("accuracy-only matrix was accepted")
    except E.AccuracyOnlyError:
        pass

    bundle = E.run_bundle()
    matrix = bundle["matrix"]
    E.validate_matrix(matrix)
    under = matrix["under_grade"]
    over = matrix["over_grade"]
    if under["count"] < 1:
        return fail("under_grade count is 0; direction split is vacuous")
    if over["count"] < 1:
        return fail("over_grade count is 0; direction split is vacuous")
    if "accuracy" in matrix and under["count"] + over["count"] == 0:
        return fail("accuracy published without directional errors")

    controls = bundle["controls"]
    planted = str(controls["planted_under_grade_id"])
    expected_under = set(controls["under_grade_ids"])
    expected_over = set(controls["over_grade_ids"])
    if set(under["ids"]) != expected_under:
        return fail(f"under ids {under['ids']} != {sorted(expected_under)}")
    if set(over["ids"]) != expected_over:
        return fail(f"over ids {over['ids']} != {sorted(expected_over)}")

    before = set(bundle["census_before"])
    after = set(bundle["census_after"])
    missing_before = expected_under - before
    if missing_before != expected_under:
        return fail(f"under-grades already in author census: {sorted(expected_under - missing_before)}")
    if planted in before:
        return fail("planted under-grade already in author census")
    if not expected_under.issubset(after):
        return fail(f"re-inject missed {sorted(expected_under - after)}")
    if planted not in after:
        return fail("planted claim absent from re-injected census")

    reviewer = bundle["reviewer_rows"]
    if len(reviewer) < 10:
        return fail(f"reviewer re-graded {len(reviewer)} claims; need >=10")
    mismatch = [
        r["claim_id"]
        for r, s in zip(bundle["rows"], reviewer)
        if r["independent_severity"] != s["independent_severity"]
    ]
    if mismatch:
        return fail(f"statement-only reviewer disagreed on {mismatch}")

    art_matrix = doc.get("disagreement_matrix") or {}
    if art_matrix.get("under_grade", {}).get("count") != under["count"]:
        return fail("artifact under_grade count drifted")
    if art_matrix.get("over_grade", {}).get("count") != over["count"]:
        return fail("artifact over_grade count drifted")
    art_after = set(doc.get("census_after_reinject") or doc.get("census_after") or [])
    if not expected_under.issubset(art_after):
        return fail("artifact census_after missing re-injected ids")

    print(
        json.dumps(
            {
                "probe": "probe2-direction-and-reinject",
                "unit_id": "CNF-0142",
                "accuracy_only_rejected": True,
                "under_grade": under["count"],
                "over_grade": over["count"],
                "agree": matrix["agree"]["count"],
                "accuracy": matrix["accuracy"],
                "dangerous_error_share": matrix["dangerous_error_share"],
                "census_before": sorted(before),
                "census_after": sorted(after),
                "reinjected": sorted(expected_under),
                "planted_in_census_before": planted in before,
                "planted_in_census_after": planted in after,
                "reviewer_n": len(reviewer),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"under={under['count']} over={over['count']} "
        f"census {len(before)}->{len(after)} plant_in_after=True"
    )
    print("SUCCESS:CNF-0142-probe2 direction split and census re-injection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
