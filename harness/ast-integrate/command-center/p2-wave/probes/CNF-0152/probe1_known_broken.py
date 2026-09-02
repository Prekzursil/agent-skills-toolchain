#!/usr/bin/env python3
"""Probe 1: known-broken control — each catalog shape breaks a naive impl."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from matrix import run_matrix  # noqa: E402

OUT = HERE / "probe1-known-broken.raw.json"


def main() -> int:
    result = run_matrix(HERE / "work")
    rows = result["catalog_shapes"]
    payload = {
        "probe": "probe1-known-broken",
        "unit_id": "CNF-0152",
        "known_broken_control": result["known_broken_control"],
        "rows": [
            {
                "shape_id": r["shape_id"],
                "path_used": r["path_used"],
                "oracle_count": r["oracle_count"],
                "naive_count": r["naive"]["count"],
                "naive_error": r["naive"]["error"],
                "naive_breaks": r["naive"]["breaks_shape"],
                "why": r["naive"]["why"],
                "verbatim": r["verbatim_naive_error_or_pass"],
            }
            for r in rows
        ],
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    failed = [r for r in rows if not r["naive"]["breaks_shape"]]
    if failed:
        print("FAILED:CNF-0152-probe1 naive did not break: " + ",".join(f["shape_id"] for f in failed))
        return 1
    if not result["known_broken_control"]["pass"]:
        print("FAILED:CNF-0152-probe1 known-broken control")
        return 1
    for r in rows:
        print(
            f"{r['shape_id']} naive_breaks={r['naive']['breaks_shape']} "
            f"oracle={r['oracle_count']} naive_count={r['naive']['count']} "
            f"path={r['path_used']}"
        )
        print(f"  verbatim={r['verbatim_naive_error_or_pass']}")
    print("SUCCESS:CNF-0152-probe1 known-broken control: each of five shapes breaks naive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
