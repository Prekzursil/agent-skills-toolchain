#!/usr/bin/env python3
"""Probe 1: oracle has 12 independently-addressable, distinguishable conditions."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from case import snapshot_from_case  # noqa: E402
from conditions import CONDITION_IDS  # noqa: E402
from corpus import cases, isolation_cases  # noqa: E402
import oracle as O  # noqa: E402


def main() -> int:
    missing = [cid for cid in CONDITION_IDS if cid not in O.CHECKS]
    extra = [cid for cid in O.CHECKS if cid not in CONDITION_IDS]
    if missing or extra:
        print(f"FAILED:TST-0001-probe1 check-map missing={missing} extra={extra}")
        return 1
    if len(O.CHECKS) != 12:
        print(f"FAILED:TST-0001-probe1 expected 12 checks got {len(O.CHECKS)}")
        return 1

    seen: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="tst0001-p1-") as tmp:
        root = Path(tmp)
        for case in isolation_cases():
            snap = snapshot_from_case(case, root / case["id"])
            vector = O.evaluate_all(snap)
            verdict = O.verdict(snap)
            expect = case["expect_failing_condition_id"]
            cid = verdict.get("failing_condition_id")
            print(
                f"isolation {case['id']} expect={expect} got={cid} "
                f"vector_false={[k for k, v in vector.items() if not v]}"
            )
            if verdict.get("verdict") != "FAIL":
                print(f"FAILED:TST-0001-probe1 {case['id']} did not FAIL")
                return 1
            if cid != expect:
                print(f"FAILED:TST-0001-probe1 {case['id']} id {cid!r} != {expect!r}")
                return 1
            if vector.get(expect) is not False:
                print(f"FAILED:TST-0001-probe1 {case['id']} check {expect} was not False")
                return 1
            if cid in seen:
                print(
                    f"FAILED:TST-0001-probe1 duplicate id {cid} ({seen[cid]} and {case['id']})"
                )
                return 1
            seen[cid] = case["id"]

        pass_case = next(c for c in cases() if c["id"] == "pass-control")
        snap = snapshot_from_case(pass_case, root / "pass-control")
        vector = O.evaluate_all(snap)
        verdict = O.verdict(snap)
        print(f"pass-control verdict={verdict['verdict']} vector={vector}")
        if verdict.get("verdict") != "PASS" or verdict.get("failing_condition_id") is not None:
            print("FAILED:TST-0001-probe1 pass-control did not PASS")
            return 1
        if not all(vector[cid] is True for cid in CONDITION_IDS):
            print(f"FAILED:TST-0001-probe1 pass-control vector not all True: {vector}")
            return 1

    if set(seen) != set(CONDITION_IDS):
        print(f"FAILED:TST-0001-probe1 ids {sorted(seen)} != {list(CONDITION_IDS)}")
        return 1
    print(
        json.dumps(
            {"distinct_failing_condition_ids": sorted(seen), "n": len(seen)},
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:TST-0001-probe1 oracle has 12 distinguishable independently-addressable conditions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
