#!/usr/bin/env python3
"""Probe 2: session occupancy of the packed turn-0 blob vs per-file sum.

This is a different instrument from probe 1: one concatenated payload is
tokenized once. A large unexplained gap means the enumeration is incomplete
and must not be reported as a budget.

Control (both states):
  good — full injection set: |sum - occupancy| <= stated tolerance
  bad  — drop the dominant injected item from the file sum; gap exceeds
          tolerance, so a missing file cannot be folded into a budget
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from injection import (  # noqa: E402
    UNIT,
    TOKENIZER_ID,
    file_token_sum,
    injected_only,
    injection_set,
    session_occupancy_tokens,
    tolerance_tokens,
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    items = injection_set()
    inj = injected_only(items)
    if len(inj) < 2:
        return fail(f"need >=2 injected items, got {len(inj)}")

    file_sum = file_token_sum(inj)
    occupancy, blob = session_occupancy_tokens(inj)
    gap = abs(file_sum - occupancy)
    tol = tolerance_tokens(len(inj), file_sum)
    if file_sum <= 0 or occupancy <= 0:
        return fail("zero occupancy or file sum")
    if gap > tol:
        return fail(
            f"full-set gap {gap} exceeds tolerance {tol} "
            f"(sum={file_sum} occupancy={occupancy}); enumeration is not a budget"
        )

    dominant = max(inj, key=lambda r: int(r["tokens"]))
    withheld = [r for r in inj if r["path"] != dominant["path"]]
    withheld_sum = file_token_sum(withheld)
    withheld_gap = abs(withheld_sum - occupancy)
    if withheld_gap <= tol:
        return fail(
            f"withholding {dominant['path']} ({dominant['tokens']} tokens) "
            f"did not open a gap above tolerance {tol} (gap={withheld_gap})"
        )
    if withheld_sum >= file_sum:
        return fail("withheld sum did not drop")

    report = {
        "probe": "probe2-session-occupancy",
        "unit_id": UNIT,
        "tokenizer_id": TOKENIZER_ID,
        "instrument": "packed-session-blob-token-count",
        "injected_count": len(inj),
        "file_token_sum": file_sum,
        "session_occupancy_tokens": occupancy,
        "occupancy_bytes": len(blob.encode("utf-8")),
        "gap_tokens": gap,
        "tolerance_tokens": tol,
        "within_tolerance": True,
        "qualifies_as_budget": True,
        "withheld": {
            "path": dominant["path"],
            "tokens": dominant["tokens"],
            "withheld_file_sum": withheld_sum,
            "gap_vs_full_occupancy": withheld_gap,
            "exceeds_tolerance": True,
        },
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"SUCCESS:{UNIT}-probe2 occupancy={occupancy} sum={file_sum} "
        f"gap={gap}<={tol}; withheld {dominant['path']} gap={withheld_gap}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
