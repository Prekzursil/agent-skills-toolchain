#!/usr/bin/env python3
"""Probe 2: both-states, silent-zero, case-collision, independent sixth shape."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from matrix import run_matrix  # noqa: E402

OUT = HERE / "probe2-both-states.raw.json"


def main() -> int:
    result = run_matrix(HERE / "work")
    payload = {
        "probe": "probe2-both-states",
        "unit_id": "CNF-0152",
        "both_states": result["both_states"],
        "silent_zero_control": result["silent_zero_control"],
        "case_collision_control": result["case_collision_control"],
        "reviewer_sixth": result["reviewer_sixth"],
        "rows": [
            {
                "shape_id": r["shape_id"],
                "path_used": r["path_used"],
                "both_states": r["both_states"],
                "naive_breaks": r["naive"]["breaks_shape"],
                "hardened_passes": r["hardened"]["passes_shape"],
                "oracle_count": r["oracle_count"],
                "naive_count": r["naive"]["count"],
                "hardened_count": r["hardened"]["count"],
                "posix_live_count": r["posix_live"]["count"],
            }
            for r in result["catalog_shapes"]
        ],
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not result["both_states"]["pass"]:
        bad = [r["shape_id"] for r in result["catalog_shapes"] if not r["both_states"]]
        print("FAILED:CNF-0152-probe2 both-states " + ",".join(bad))
        return 1
    if not result["silent_zero_control"]["pass"]:
        print("FAILED:CNF-0152-probe2 silent-zero control")
        print(json.dumps(result["silent_zero_control"], indent=2)[:1500])
        return 1
    if not result["case_collision_control"]["pass"]:
        print("FAILED:CNF-0152-probe2 case-collision control")
        print(json.dumps(result["case_collision_control"], indent=2)[:1500])
        return 1
    sixth = result["reviewer_sixth"]
    if not sixth["naive_breaks"] or not sixth["hardened_passes"]:
        print("FAILED:CNF-0152-probe2 sixth shape did not split naive/hardened")
        print(json.dumps(sixth, indent=2)[:1500])
        return 1

    sz = result["silent_zero_control"]
    cc = result["case_collision_control"]
    print(
        f"both_states={result['both_states']['pass']} "
        f"silent_zero naive={sz['naive_count']} hardened={sz['hardened_count']} "
        f"oracle={sz['oracle_count']}"
    )
    print(
        f"case_collision naive={cc['naive_count']} hardened={cc['hardened_count']} "
        f"oracle={cc['oracle_count']}"
    )
    print(
        f"sixth={sixth['shape_id']} naive_breaks={sixth['naive_breaks']} "
        f"hardened_passes={sixth['hardened_passes']} path={sixth['path_used']}"
    )
    print("SUCCESS:CNF-0152-probe2 both-states silent-zero case-collision sixth-shape")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
