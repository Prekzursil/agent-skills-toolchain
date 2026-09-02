#!/usr/bin/env python3
"""Probe 2: negative control — present-only averaging reducer must fail.

Mechanically different from probe 1: this probe never treats the production
reducer's verdict as the thing under test. It plants a reducer that computes
over present shards only, feeds it the 3-of-4 set, and requires that reducer
to FAIL the TST-0148 contract (INCOMPLETE with the missing id enumerated).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
from present_only import reduce_present_only  # noqa: E402


def contract_holds(result: dict, expected_missing: list[str]) -> bool:
    """TST-0148 contract: missing shards named, never averaged away."""
    if expected_missing:
        missing = result.get("missing_ids")
        return (
            result.get("status") == "INCOMPLETE"
            and isinstance(missing, list)
            and all(mid in missing for mid in expected_missing)
            and result.get("computed_over_present") is not True
        )
    return (
        result.get("status") == "COMPLETE"
        and list(result.get("missing_ids") or []) == []
    )


def main() -> int:
    F.materialize_ondisk()
    with tempfile.TemporaryDirectory(prefix="tst-0148-p2-") as tmp:
        tmp_path = Path(tmp)
        complete_root, complete_man = F.populate_tree(tmp_path / "all-four")
        incomplete_root, incomplete_man = F.populate_tree(
            tmp_path / "three-of-four", omit=F.MISSING_ID
        )
        bad_on_incomplete = reduce_present_only(incomplete_root, incomplete_man)
        bad_on_complete = reduce_present_only(complete_root, complete_man)

        planted_fails_contract = not contract_holds(
            bad_on_incomplete, [F.MISSING_ID]
        )
        names_missing = F.MISSING_ID in list(bad_on_incomplete.get("missing_ids") or [])
        averaged = (
            bad_on_incomplete.get("status") == "COMPLETE"
            and bad_on_incomplete.get("computed_over_present") is True
            and "missing_ids" not in bad_on_incomplete
        )
        silent_on_full_set = bad_on_complete.get("status") == "COMPLETE"

        ok = (
            planted_fails_contract
            and averaged
            and not names_missing
            and silent_on_full_set
            and bad_on_incomplete.get("score") == 1.0
        )
        report = {
            "probe": "probe2-present-only-control",
            "unit_id": "TST-0148",
            "pass": ok,
            "fired_on_bad_state": planted_fails_contract,
            "silent_on_good_state": silent_on_full_set,
            "planted_reducer": "present-only-average",
            "present_only_on_3_of_4": bad_on_incomplete,
            "present_only_on_all_4": {
                "status": bad_on_complete.get("status"),
                "score": bad_on_complete.get("score"),
                "computed_over_present": bad_on_complete.get("computed_over_present"),
            },
            "does_on_reject_state": (
                "FIRES: present-only returns COMPLETE with score=1.0 on 3 of 4 "
                f"shards and omits missing_ids so {F.MISSING_ID} is averaged away."
            ),
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        if not ok:
            print("FAILED:TST-0148-probe2 present-only reducer was not rejected")
            return 1
        print(
            "SUCCESS:TST-0148-probe2 present-only averaging reducer failed "
            "the missing-shard contract"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
