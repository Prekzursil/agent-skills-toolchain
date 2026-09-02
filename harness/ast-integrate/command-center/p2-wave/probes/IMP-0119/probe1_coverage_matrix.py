#!/usr/bin/env python3
"""Named probe 1: coverage matrix — each bad fixture trips exactly one gate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def repo_root() -> Path:
    cur = HERE
    for _ in range(8):
        if (cur / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return cur
        cur = cur.parent
    raise SystemExit("FAILED:IMP-0119-probe1 repo root not found")


REPO = repo_root()
sys.path.insert(0, str(REPO / "tools"))

from marketplace.corpus import BAD_EXPECTED, GOOD_IDS, load_corpus, materialize  # noqa: E402
from marketplace.gates import coverage_matrix  # noqa: E402


def main() -> int:
    materialize()
    packages = load_corpus()
    matrix = coverage_matrix(packages)
    bad_fail = []
    for fid, expected in BAD_EXPECTED.items():
        fired = matrix.get(fid)
        if fired != [expected]:
            bad_fail.append({"fixture": fid, "expected": expected, "fired": fired})
    good_fail = [
        {"fixture": fid, "fired": matrix.get(fid)}
        for fid in GOOD_IDS
        if matrix.get(fid)
    ]
    silent = [fid for fid in BAD_EXPECTED if not matrix.get(fid)]
    payload = {
        "probe": "probe1-coverage-matrix",
        "unit_id": "IMP-0119",
        "bad_count": len(BAD_EXPECTED),
        "good_count": len(GOOD_IDS),
        "matrix": matrix,
        "exactly_one_gate_per_bad": not bad_fail,
        "no_good_trips": not good_fail,
        "no_silent_bad": not silent,
        "pass": not bad_fail and not good_fail and not silent,
    }
    print(json.dumps(payload, sort_keys=True))
    if bad_fail:
        print(f"FAILED:IMP-0119-probe1 bad_mismatch {bad_fail}")
        return 1
    if good_fail:
        print(f"FAILED:IMP-0119-probe1 good_tripped {good_fail}")
        return 1
    if silent:
        print(f"FAILED:IMP-0119-probe1 silent_all_gates {silent}")
        return 1
    print(
        f"matrix bad={len(BAD_EXPECTED)} good={len(GOOD_IDS)} "
        "exactly_one=True silent_bad=0"
    )
    print("SUCCESS:IMP-0119-probe1 coverage matrix both directions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
