#!/usr/bin/env python3
"""Probe 2: mention without mutation is CLAIMED-NOT-PROVEN; reviewer re-derives uncovered."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import classes as C  # noqa: E402
import controls as CTL  # noqa: E402
import inventory as I  # noqa: E402
import mapper as M  # noqa: E402
import schema_local as S  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0047.failure-class-coverage.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0047-probe2 {msg}")
    return 1


def main() -> int:
    claimed = CTL.assert_claimed_not_proven()
    if claimed["status"] == M.COVERED:
        return fail("unproven mention counted COVERED")

    classes, tests, _mutations = CTL.claimed_unproven_inputs()
    cheat_mutations = [
        {
            "test_id": tests[0]["id"],
            "result": "FIRED",
            "broken_fails": True,
            "good_passes": True,
        }
    ]
    cheated = M.map_classes(classes, tests, cheat_mutations, [])[0]
    if cheated["status"] != M.COVERED:
        return fail("positive control: planted FIRED mutation did not yield COVERED")

    extracted = C.extract_classes(REPO)
    inv = I.collect_inventory(REPO)
    live_rows = M.map_classes(
        extracted["classes"], inv["tests"], inv["mutations"], inv["causes"]
    )
    live_uncovered = M.uncovered_rows(live_rows)
    live_unmatched = M.unmatched_causes(inv["causes"], live_rows)

    if not ART.is_file():
        return fail("artifact missing")
    raw = json.loads(ART.read_text(encoding="utf-8"))
    doc = S.payload(raw)
    art_uncovered = {u.get("id") for u in (doc.get("uncovered") or [])}
    if art_uncovered != {u["id"] for u in live_uncovered}:
        return fail("reviewer uncovered set disagrees with artifact")
    art_unmatched = {u.get("id") for u in (doc.get("unmatched_root_causes") or [])}
    if art_unmatched != {u["id"] for u in live_unmatched}:
        return fail("reviewer unmatched-cause set disagrees with artifact")

    for row in live_rows:
        if row["status"] == M.COVERED and not row.get("proven_tests"):
            return fail(f"{row['id']} COVERED without proven_tests")
        if row["status"] == M.CLAIMED and row.get("proven_tests"):
            return fail(f"{row['id']} CLAIMED-NOT-PROVEN but has proven_tests")

    print(
        json.dumps(
            {
                "claimed_not_proven_status": claimed["status"],
                "planted_fired_is_covered": cheated["status"] == M.COVERED,
                "live_uncovered": len(live_uncovered),
                "live_unmatched_causes": len(live_unmatched),
                "syn0001_present": inv["syn0001"]["present"],
                "cc0014_present": inv["cc0014"]["present"],
                "reviewer_rederived_before_conclusion": True,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:SYN-0047-probe2 CLAIMED-NOT-PROVEN control; reviewer re-derived uncovered set"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
