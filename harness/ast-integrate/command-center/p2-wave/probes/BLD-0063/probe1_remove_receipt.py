#!/usr/bin/env python3
"""Probe 1: remove one BLD receipt in a scratch copy; coverage must drop."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
from matrix import compute_matrix, write_scratch_receipt  # noqa: E402
from questions import ELEVEN, first_unit_for_each_question, load_catalog_units  # noqa: E402

CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"


def main() -> int:
    catalog_units = load_catalog_units(CATALOG)
    first = first_unit_for_each_question(catalog_units)
    if len(first) != 11:
        print(f"FAILED:BLD-0063-probe1 expected 11 first-units got {len(first)}")
        return 1

    with tempfile.TemporaryDirectory(prefix="bld0063-p1-") as tmp:
        receipts = Path(tmp)
        for _qid, label in ELEVEN:
            uid = first[label]
            write_scratch_receipt(receipts, uid, label, ["CONFIRMED"])
        before = compute_matrix(CATALOG, receipts)
        if before["uncovered_questions"]:
            print(
                "FAILED:BLD-0063-probe1 full scratch should be all COVERED "
                f"uncovered={before['uncovered_questions']}"
            )
            return 1
        if len(before["covered_questions"]) != 11:
            print(
                "FAILED:BLD-0063-probe1 covered "
                f"{len(before['covered_questions'])} != 11"
            )
            return 1

        drop_label = ELEVEN[0][1]
        drop_uid = first[drop_label]
        (receipts / f"{drop_uid}.json").unlink()
        after = compute_matrix(CATALOG, receipts)

        after_cov = {row["question"]: row["coverage"] for row in after["questions"]}
        print(f"removed {drop_uid} for {drop_label}")
        print(f"before_covered={len(before['covered_questions'])}")
        print(f"after_covered={len(after['covered_questions'])}")
        print(f"after[{drop_label}]={after_cov.get(drop_label)}")

        if after_cov.get(drop_label) != "UNCOVERED":
            print("FAILED:BLD-0063-probe1 dropped question did not become UNCOVERED")
            return 1
        if drop_label not in after["uncovered_questions"]:
            print("FAILED:BLD-0063-probe1 dropped question missing from uncovered list")
            return 1
        if len(after["covered_questions"]) != 10:
            print("FAILED:BLD-0063-probe1 sibling coverage changed unexpectedly")
            return 1
        for _qid, label in ELEVEN[1:]:
            if after_cov.get(label) != "COVERED":
                print(f"FAILED:BLD-0063-probe1 sibling {label} not COVERED")
                return 1
        if after["receipts_read"] != before["receipts_read"] - 1:
            print(
                "FAILED:BLD-0063-probe1 receipts_read did not drop "
                f"{before['receipts_read']} -> {after['receipts_read']}"
            )
            return 1

    print("SUCCESS:BLD-0063-probe1 remove-receipt coverage drop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
