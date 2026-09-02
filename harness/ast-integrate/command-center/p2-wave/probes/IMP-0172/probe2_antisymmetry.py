#!/usr/bin/env python3
"""Probe 2: antisymmetry over the fixture matrix.

Catalog tests_required[1] and evidence signal (2): reverse(diff(a,b)) equals
diff(b,a), computed — not asserted by inspection.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import semantic_diff as D  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0172.json"


def main() -> int:
    matrix = F.fixture_matrix()
    rows = []
    failures = []
    expected = {
        "identical": "IDENTICAL",
        "rename-only": "IDENTICAL",
        "both-sides-unique": "DIVERGED",
        "left-ahead": "LEFT-AHEAD",
        "right-ahead": "RIGHT-AHEAD",
        "gate-change": "DIVERGED",
        "role-change": "DIVERGED",
        "tool-change": "DIVERGED",
    }
    for name, a, b in matrix:
        ab = D.diff_workflows(a, b)
        ba = D.diff_workflows(b, a)
        rev = D.reverse_diff(ab)
        equal = D.diffs_equal(rev, ba)
        want = expected[name]
        ok = equal and ab["verdict"] == want
        rows.append(
            {
                "pair": name,
                "verdict_ab": ab["verdict"],
                "verdict_ba": ba["verdict"],
                "verdict_rev": rev["verdict"],
                "expected": want,
                "antisymmetric": equal,
                "pass": ok,
            }
        )
        if not ok:
            failures.append(name)
            print(f"FAIL pair={name} ab={ab['verdict']} ba={ba['verdict']} equal={equal} want={want}")
            if not equal:
                print("  canonical reverse(ab) vs ba:")
                print("  rev", json.dumps(D.canonical_diff(rev), sort_keys=True)[:500])
                print("  ba ", json.dumps(D.canonical_diff(ba), sort_keys=True)[:500])
        else:
            print(
                f"ok pair={name} verdict={ab['verdict']} "
                f"reverse={rev['verdict']} antisymmetric=true"
            )

    passed = sum(1 for r in rows if r["pass"])
    print(
        json.dumps(
            {
                "probe": "probe2-antisymmetry",
                "unit_id": "IMP-0172",
                "pairs": len(matrix),
                "passed": passed,
                "failed": failures,
            },
            sort_keys=True,
        )
    )
    if failures:
        print(f"FAILED:IMP-0172-probe2 antisymmetry failures {failures}")
        return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:IMP-0172" not in text:
            print("FAILED:IMP-0172-probe2 receipt sentinel absent")
            return 1

    print(f"SUCCESS:IMP-0172-probe2 antisymmetry {passed}/{len(matrix)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
