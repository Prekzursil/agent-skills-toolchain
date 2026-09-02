#!/usr/bin/env python3
"""Probe 1: planted conformity, corroboration, and shared-stale-ancestor labels."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from attribute import attribute_scenario, required_planted  # noqa: E402

EXPECT = {
    "planted-conformity": "CONFORMITY",
    "planted-corroboration": "CORROBORATED",
    "planted-shared-stale-ancestor": "CONFORMITY",
}


def main() -> int:
    rows = []
    for scenario in required_planted():
        result = attribute_scenario(scenario, join="identity")
        sid = result["id"]
        want = EXPECT.get(sid)
        got = result["observed_label"]
        ok = want == got == result["expected_label"] and result["correct"] is True
        rows.append(
            {
                "id": sid,
                "expected": want,
                "observed": got,
                "lca": result["lowest_common_ancestors"],
                "ok": ok,
            }
        )
        print(f"{sid} expected={want} observed={got} lca={result['lowest_common_ancestors']} ok={ok}")
        if not ok:
            print(f"FAILED:SYN-0023-probe1 {sid}")
            return 1
        if sid == "planted-conformity" and not result["lowest_common_ancestors"]:
            print("FAILED:SYN-0023-probe1 conformity produced empty LCA")
            return 1
        if sid == "planted-corroboration" and result["lowest_common_ancestors"]:
            print("FAILED:SYN-0023-probe1 corroboration produced a shared ancestor")
            return 1
        if sid == "planted-shared-stale-ancestor":
            if not result["lowest_common_ancestors"]:
                print("FAILED:SYN-0023-probe1 stale-ancestor missed the shared root")
                return 1
            if result["independent_lineage_count"] != 1:
                print("FAILED:SYN-0023-probe1 stale-ancestor counted as independent")
                return 1
    if len(rows) != 3:
        print(f"FAILED:SYN-0023-probe1 expected 3 planted cases got {len(rows)}")
        return 1
    print(json.dumps({"probe": "probe1-planted-labels", "rows": rows, "pass": True}))
    print("SUCCESS:SYN-0023-probe1 planted conformity, corroboration, stale-ancestor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
