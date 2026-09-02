#!/usr/bin/env python3
"""Probe 1: historical false-positive corpus -> zero role flags.

Naive payload-text matching must still fire on every record (detector
control: the test can see the false-positive class). Role matching must
fire on none. Both rebuilt scanners are reported separately. Silencing
true positives to clear this corpus is checked by probe 2, not here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from evaluate import evaluate_scanners  # noqa: E402

SENTINEL = "SUCCESS:TST-0341"


def main() -> int:
    ev = evaluate_scanners()
    fx = ev["fixture"]["false_positive"]
    ct = ev["content"]["false_positive"]
    print(
        json.dumps(
            {
                "probe": "probe1-historical-fp",
                "historical_n": ev["historical_n"],
                "fixture": fx,
                "content": ct,
            },
            sort_keys=True,
        )
    )
    if ev["historical_n"] < 8:
        print("FAILED:TST-0341-probe1 historical corpus smaller than the measured eight hits")
        return 1
    if fx["n"] < 1 or ct["n"] < 1:
        print("FAILED:TST-0341-probe1 a rebuilt scanner saw an empty FP split")
        return 1
    if fx["role_fires"] != 0:
        print(f"FAILED:TST-0341-probe1 fixture scanner still flags {fx['role_fires_ids']}")
        return 1
    if ct["role_fires"] != 0:
        print(f"FAILED:TST-0341-probe1 content scanner still flags {ct['role_fires_ids']}")
        return 1
    if fx["naive_fires"] != fx["n"]:
        print("FAILED:TST-0341-probe1 fixture naive matcher did not fire on every mention (inert control)")
        return 1
    if ct["naive_fires"] != ct["n"]:
        print("FAILED:TST-0341-probe1 content naive matcher did not fire on every mention (inert control)")
        return 1
    if not fx["ok"] or not ct["ok"]:
        print("FAILED:TST-0341-probe1 historical FP not clean")
        return 1
    print(
        f"fixture_fp n={fx['n']} role_fires=0 naive={fx['naive_fires']} "
        f"content_fp n={ct['n']} role_fires=0 naive={ct['naive_fires']}"
    )
    print("SUCCESS:TST-0341-probe1 historical false-positive corpus is silent under role matching")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
