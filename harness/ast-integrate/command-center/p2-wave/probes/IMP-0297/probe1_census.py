#!/usr/bin/env python3
"""Probe 1: 58-protocol expressibility census.

Recomputes classification from records. Requires n=58, unique P01..P58,
inexpressible ids named with reasons, and no full-coverage claim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.protocol.plugin import census, load_protocols  # noqa: E402

EXPECTED_BLOCKED = ("P32", "P34", "P48", "P52", "P54", "P55", "P58")


def main() -> int:
    rows = load_protocols()
    ids = [r["id"] for r in rows]
    expected = [f"P{i:02d}" for i in range(1, 59)]
    if ids != expected:
        print("FAILED:IMP-0297-probe1 id sequence", ids[:5], "...", ids[-3:])
        return 1
    result = census()
    if result["n"] != 58:
        print("FAILED:IMP-0297-probe1 n", result["n"])
        return 1
    if result.get("full_coverage_claim") is not False:
        print("FAILED:IMP-0297-probe1 overclaim full coverage")
        return 1
    if result.get("library_file_present") is not False:
        print("FAILED:IMP-0297-probe1 library file was not on disk but census claimed it")
        return 1
    blocked = result["needs_kernel_change"]
    blocked_ids = [row["id"] for row in blocked]
    if tuple(blocked_ids) != EXPECTED_BLOCKED:
        print("FAILED:IMP-0297-probe1 blocked set", blocked_ids, "want", EXPECTED_BLOCKED)
        return 1
    if result["expressible_n"] + result["needs_kernel_change_n"] != 58:
        print("FAILED:IMP-0297-probe1 partition", result["expressible_n"], result["needs_kernel_change_n"])
        return 1
    for row in blocked:
        if not row.get("extra_primitives") or not row.get("reasons"):
            print("FAILED:IMP-0297-probe1 unnamed inexpressible", row)
            return 1
        if row["status"] != "needs-kernel-change":
            print("FAILED:IMP-0297-probe1 status", row)
            return 1
    print(json.dumps({
        "n": result["n"],
        "expressible_n": result["expressible_n"],
        "needs_kernel_change_n": result["needs_kernel_change_n"],
        "needs_kernel_change_ids": blocked_ids,
        "library_file_present": result["library_file_present"],
        "full_coverage_claim": result["full_coverage_claim"],
    }, indent=2))
    print(
        "census 58 "
        f"expressible={result['expressible_n']} "
        f"needs-kernel-change={result['needs_kernel_change_n']} "
        f"named={blocked_ids}"
    )
    print("SUCCESS:IMP-0297-probe1 census 58 named inexpressible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
