#!/usr/bin/env python3
"""Named probe 1: re-run the cancelling-pair detector control on the fixtures.

A reviewer who only re-reads the artifact has verified nothing. This probe
re-executes both fixture trees and recomputes the set difference.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import domain_payload, run_unittest_tree  # noqa: E402
from outcome_set import (  # noqa: E402
    FLIP_TO_FAIL_ID,
    FLIP_TO_PASS_ID,
    cancelling_pair_holds,
)

ART = REPO / "command-center/confirmation/CNF-0051-outcome-set-diff.json"
BEFORE = HERE / "fixtures" / "cancelling" / "before"
AFTER = HERE / "fixtures" / "cancelling" / "after"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0051-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0051":
        print("FAILED:CNF-0051-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:CNF-0051" not in text:
        print("FAILED:CNF-0051-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0051-probe1 self-declared", st)
        return 1

    before = run_unittest_tree(BEFORE)
    after = run_unittest_tree(AFTER)
    pair = cancelling_pair_holds(before, after)
    payload = {
        "probe": "probe1-cancelling-pair",
        "unit_id": "CNF-0051",
        "pass": bool(pair["holds"]),
        "aggregate_count_unchanged": pair["aggregate_count_unchanged"],
        "set_difference_nonempty": pair["set_difference_nonempty"],
        "flipped_each_way": pair["flipped_each_way"],
        "visible_counts_before": pair["visible_counts_before"],
        "visible_counts_after": pair["visible_counts_after"],
        "flipped": pair["symmetric_difference"]["flipped"],
        "counts": pair["symmetric_difference"]["counts"],
    }
    print(json.dumps(payload, sort_keys=True))
    if not pair["holds"]:
        print("FAILED:CNF-0051-probe1 cancelling-pair control did not fire")
        return 1
    flipped = {f["id"]: (f["from"], f["to"]) for f in pair["symmetric_difference"]["flipped"]}
    if flipped.get(FLIP_TO_FAIL_ID) != ("passed", "failed"):
        print("FAILED:CNF-0051-probe1 expected pass->fail missing", flipped)
        return 1
    if flipped.get(FLIP_TO_PASS_ID) != ("failed", "passed"):
        print("FAILED:CNF-0051-probe1 expected fail->pass missing", flipped)
        return 1
    if pair["visible_counts_before"]["passed"] != pair["visible_counts_after"]["passed"]:
        print("FAILED:CNF-0051-probe1 pass count moved; not a cancelling pair")
        return 1
    if pair["visible_counts_before"]["failed"] != pair["visible_counts_after"]["failed"]:
        print("FAILED:CNF-0051-probe1 fail count moved; not a cancelling pair")
        return 1
    ctrl = ((domain_payload(doc).get("controls") or {}).get("cancelling_pair") or {})
    if ctrl.get("invisible_to_counts_visible_to_set_difference") is not True:
        print("FAILED:CNF-0051-probe1 artifact did not record the control proof")
        return 1
    print(
        "visible_counts",
        pair["visible_counts_before"],
        "flipped_to_fail",
        FLIP_TO_FAIL_ID,
        "flipped_to_pass",
        FLIP_TO_PASS_ID,
    )
    print("SUCCESS:CNF-0051-probe1 cancelling-pair invisible to counts, visible to set difference")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
