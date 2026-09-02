#!/usr/bin/env python3
"""Probe 1: largest-artifact full-parse at 1x and synthetic 10x (measured)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import PARSE_BUDGET_MS, largest_json, measure_parse_pair  # noqa: E402

ART = REPO / "command-center" / "receipts" / "BLD-0056.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0056-probe1 {msg}")
    return 1


def main() -> int:
    largest = largest_json(REPO)
    if not largest["present"]:
        return fail("no largest JSON on disk")
    src = REPO / largest["path"]
    if not src.is_file():
        return fail(f"missing {largest['path']}")
    parsed = measure_parse_pair(src)
    x1 = parsed["x1"]
    x10 = parsed["x10"]
    if x1["kind"] != "MEASURED" or x10["kind"] != "MEASURED":
        return fail("parse times were not MEASURED")
    if x1["file_bytes"] < 1:
        return fail("1x file empty")
    if x10["file_bytes"] < x1["file_bytes"] * 9:
        return fail(
            f"10x bytes {x10['file_bytes']} not ~10x of {x1['file_bytes']}"
        )
    rec = parsed["reader_recommendation"]
    expect = (
        "stream-or-paginate"
        if x10["parse_ms"] > PARSE_BUDGET_MS
        else "full-parse-ok"
    )
    if rec != expect:
        return fail(f"recommendation {rec} != {expect}")
    if rec == "stream-or-paginate" and x10["parse_ms"] <= PARSE_BUDGET_MS:
        return fail("stream recommendation without exceeding threshold")
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        budget = doc.get("parse_budget") or {}
        if str(budget.get("source") or "") != parsed["source"]:
            return fail("receipt parse source mismatch")
        if str(budget.get("reader_recommendation") or "") != rec:
            return fail("receipt reader_recommendation mismatch vs live rule")
        rx1 = (budget.get("x1") or {}).get("file_bytes")
        rx10 = (budget.get("x10") or {}).get("file_bytes")
        if rx1 != x1["file_bytes"] or rx10 != x10["file_bytes"]:
            return fail("receipt parse file_bytes mismatch vs live inflate")
    print(
        json.dumps(
            {
                "source": parsed["source"],
                "x1_bytes": x1["file_bytes"],
                "x1_ms": x1["parse_ms"],
                "x10_bytes": x10["file_bytes"],
                "x10_ms": x10["parse_ms"],
                "threshold_ms": PARSE_BUDGET_MS,
                "recommendation": rec,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:BLD-0056-probe1 parse-budget 1x+10x MEASURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
