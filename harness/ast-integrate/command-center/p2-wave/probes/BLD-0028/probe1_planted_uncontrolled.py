#!/usr/bin/env python3
"""Probe 1: planted uncontrolled zero in a scratch receipt set must be caught.

Known-present runs first. A silent harvester is rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harvest as H  # noqa: E402
import reviewer as R  # noqa: E402

PLANTED = "PLANTED-UZERO"


def main() -> int:
    mixed = H.harvest_fixture_dir("mixed")
    print(
        json.dumps(
            {
                "probe": "probe1-planted-uncontrolled",
                "zeros": mixed["zeros_harvested"],
                "uncontrolled": mixed["uncontrolled_count"],
                "controlled": mixed["controlled_count"],
                "uncontrolled_ids": mixed["uncontrolled_ids"],
                "controlled_ids": mixed["controlled_ids"],
            },
            sort_keys=True,
        )
    )
    planted = [
        row
        for row in mixed["inventory"]
        if row["producer"] == PLANTED or PLANTED in row["id"]
    ]
    if not planted:
        print("FAILED:BLD-0028-probe1 planted uncontrolled zero was not harvested")
        return 1
    if any(row["verdict"] != "uncontrolled" for row in planted):
        print("FAILED:BLD-0028-probe1 planted zero was not classified UNCONTROLLED-ZERO")
        return 1
    files = sorted(p for p in (H.FIXTURES / "mixed").rglob("*") if p.is_file())
    review = R.grade_paths(files)
    planted_r = [i for i in review["uncontrolled_ids"] if PLANTED in i]
    if not planted_r:
        print("FAILED:BLD-0028-probe1 independent reviewer missed planted zero")
        return 1
    print(
        f"planted_caught={len(planted)} reviewer_caught={len(planted_r)} "
        f"known_present_run_first=True"
    )
    print("SUCCESS:BLD-0028-probe1 planted uncontrolled zero caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
