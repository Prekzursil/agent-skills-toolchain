#!/usr/bin/env python3
"""Probe 1: known-bad coverage, seed reproducibility, undersize not rounded."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402

SEED = M.DEFAULT_SEED


def main() -> int:
    a = M.compute(seed=SEED)
    b = M.compute(seed=SEED)
    sa = M.rates_signature(a)
    sb = M.rates_signature(b)
    print(json.dumps(sa, indent=2, sort_keys=True))
    if sa != sb:
        print("FAILED:REL-0019-probe1 same-seed rates diverged")
        return 1
    for g in a["gates"]:
        n_bad = g["n_known_bad"]
        exercised = g["known_bad_exercised"]
        fn_status = g["false_negative"]["status"]
        print(
            f"gate {g['id']} n_good={g['n_known_good']} n_bad={n_bad} "
            f"exercised={exercised} fn_status={fn_status} decision={g['promote']['decision']}"
        )
        if n_bad < 1 or not exercised:
            if fn_status != "NOT-CHECKED":
                print(f"FAILED:REL-0019-probe1 {g['id']} unmeasurable FN not NOT-CHECKED")
                return 1
            print(f"FAILED:REL-0019-probe1 {g['id']} has no known-bad fixture")
            return 1
        if g["false_positive"]["denominator"] < 1:
            print(f"FAILED:REL-0019-probe1 {g['id']} has no known-good fixture")
            return 1
        if g["false_positive"]["status"] != "MEASURED":
            print(f"FAILED:REL-0019-probe1 {g['id']} FP not MEASURED")
            return 1
        if g["false_negative"]["status"] != "MEASURED":
            print(f"FAILED:REL-0019-probe1 {g['id']} FN not MEASURED")
            return 1
        interval = g["false_negative"]["interval"]
        if not interval or interval.get("method") != "wilson":
            print(f"FAILED:REL-0019-probe1 {g['id']} missing Wilson interval")
            return 1
        if g["n_known_good"] < M.MIN_SAMPLE or g["n_known_bad"] < M.MIN_SAMPLE:
            if g["promote"]["decision"] != "SAMPLE-TOO-SMALL":
                print(f"FAILED:REL-0019-probe1 {g['id']} undersized but not flagged")
                return 1
            if g["promote"]["threshold"] is not None:
                print(f"FAILED:REL-0019-probe1 {g['id']} undersized threshold was assigned")
                return 1

    ctl = a["sample_too_small_control"]
    print(
        "undersize_control n_good={0} n_bad={1} decision={2} threshold={3}".format(
            ctl["n_known_good"],
            ctl["n_known_bad"],
            ctl["decision"],
            ctl["promote_threshold"],
        )
    )
    if ctl["decision"] != "SAMPLE-TOO-SMALL":
        print("FAILED:REL-0019-probe1 undersize control was not SAMPLE-TOO-SMALL")
        return 1
    if ctl["promote_threshold"] is not None:
        print("FAILED:REL-0019-probe1 undersize control assigned a rounded threshold")
        return 1
    if ctl["n_known_good"] >= M.MIN_SAMPLE or ctl["n_known_bad"] >= M.MIN_SAMPLE:
        print("FAILED:REL-0019-probe1 undersize control was not actually undersized")
        return 1
    print("SUCCESS:REL-0019-probe1 known-bad coverage, seed repro, undersize flag")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
