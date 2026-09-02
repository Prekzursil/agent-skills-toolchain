#!/usr/bin/env python3
"""Probe 1: estimate vs actual over 20 recorded councils; publish p90 overrun."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from corpus import recorded_councils  # noqa: E402
from tools.council.budget.preflight import (  # noqa: E402
    calibrate,
    estimate_cost,
    nearest_rank_percentile,
)


def independent_p90(values: list[float], p: float = 0.90) -> float:
    xs = sorted(float(v) for v in values)
    rank = max(1, min(len(xs), math.ceil(p * len(xs))))
    return xs[rank - 1]


def main() -> int:
    records = recorded_councils()
    if len(records) != 20:
        print(f"FAILED:IMP-0352-probe1 n={len(records)} want=20")
        return 1
    report = calibrate(records)
    if report.n != 20:
        print(f"FAILED:IMP-0352-probe1 calibrate n={report.n}")
        return 1

    for row, rec in zip(report.rows, records):
        live = estimate_cost(rec["plan"]).as_dict()
        if live != row["estimate"]:
            print(f"FAILED:IMP-0352-probe1 estimate drift {rec['id']} {live} {row['estimate']}")
            return 1

    mismatches = []
    by: dict = {}
    for dim, cal in report.by_dimension.items():
        indep = independent_p90(list(cal.ratios), 0.90)
        lib = nearest_rank_percentile(cal.ratios, 0.90)
        if abs(indep - cal.p90_overrun_ratio) > 1e-12 or abs(lib - indep) > 1e-12:
            mismatches.append((dim, indep, cal.p90_overrun_ratio, lib))
        if cal.n != 20 or not (0.0 <= cal.exceed_rate <= 1.0):
            print(f"FAILED:IMP-0352-probe1 {dim} rate={cal.exceed_rate} n={cal.n}")
            return 1
        by[dim] = {
            "exceed_count": cal.exceed_count,
            "exceed_rate": cal.exceed_rate,
            "p90_overrun_ratio": cal.p90_overrun_ratio,
        }
    if mismatches:
        print(f"FAILED:IMP-0352-probe1 p90 mismatch {mismatches}")
        return 1

    combined_ratios = [max(row["overrun_ratio"].values()) for row in report.rows]
    indep_combined = independent_p90(combined_ratios, 0.90)
    if abs(indep_combined - report.combined_p90_overrun_ratio) > 1e-12:
        print("FAILED:IMP-0352-probe1 combined p90 mismatch")
        return 1

    payload = {
        "pass": True,
        "probe": "probe1-calibration",
        "unit_id": "IMP-0352",
        "n": 20,
        "by_dimension": by,
        "combined_exceed_rate": report.combined_exceed_rate,
        "combined_p90_overrun_ratio": report.combined_p90_overrun_ratio,
        "table": [
            {
                "id": row["id"],
                "estimate": row["estimate"],
                "actual": row["actual"],
                "overrun_ratio": row["overrun_ratio"],
                "exceeded_dimensions": row["exceeded_dimensions"],
            }
            for row in report.rows
        ],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "n=20 "
        f"tokens_p90={by['tokens']['p90_overrun_ratio']:.4f} "
        f"wall_p90={by['wall_clock_seconds']['p90_overrun_ratio']:.4f} "
        f"calls_p90={by['external_calls']['p90_overrun_ratio']:.4f} "
        f"combined_p90={report.combined_p90_overrun_ratio:.4f}"
    )
    print("SUCCESS:IMP-0352-probe1 estimate-vs-actual table over 20 councils; p90 published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
