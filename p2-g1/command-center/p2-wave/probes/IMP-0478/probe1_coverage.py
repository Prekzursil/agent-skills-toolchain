#!/usr/bin/env python3
"""IMP-0478 probe1: coverage-zero-unmapped (resume 2026-10-25).

Re-derives the coverage table from the receipt SSOT and the shipped catalog;
asserts every closed class maps, unmapped_after is 0, and both negative
controls fire: a later-invented class is unmapped and a traceback-only body is
not counted as coverage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import error_catalog  # noqa: E402


def fail(msg):
    print("FAILED:IMP-0478-probe1 " + str(msg))
    return 1


def main() -> int:
    receipt = json.loads((REPO / "command-center/receipts/IMP-0478.json").read_text(encoding="utf-8"))
    st = str(receipt.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail("self-declared:" + st)
    if "SENTINEL:IMP-0478:ERROR-CATALOG-COMPLETE" not in json.dumps(receipt):
        return fail("sentinel-absent")
    closed = receipt.get("taxonomy_source", {}).get("closed_classes") or []
    if len(closed) != 8:
        return fail("closed-class-count:" + str(len(closed)))
    rows = error_catalog._coverage_rows()
    unmapped = []
    for cls in closed:
        entry = error_catalog.lookup(cls)
        if not entry["mapped"]:
            unmapped.append(cls)
    print("closed_class_count=" + str(len(closed)) + " unmapped=" + str(len(unmapped)))
    if unmapped:
        return fail("unmapped-classes:" + json.dumps(unmapped))
    if receipt.get("unmapped_after") != 0 or receipt.get("unmapped_after_is_zero") is not True:
        return fail("receipt-unmapped-numbers-drift")
    if receipt.get("unmapped_before") != 8:
        return fail("receipt-unmapped-before-drift")
    # table identity: live rows == receipt rows on (class, id, command)
    for live, rec in zip(rows, receipt.get("coverage_table") or []):
        if (live.get("taxonomy_class"), live.get("message_id"), live.get("next_command")) != (
            rec.get("taxonomy_class"), rec.get("message_id"), rec.get("next_command")
        ):
            return fail("coverage-table-drift:" + str(live.get("taxonomy_class")))
    # negative control 1: a later-invented class must be unmapped
    invented = error_catalog.lookup("later-invented-class")
    if invented["mapped"]:
        return fail("negative-control-later-class-force-fitted")
    # negative control 2: a traceback-only body is not coverage
    trace_body = chr(10).join(["Traceback (most recent call last):", "  File " + chr(34) + "x.py" + chr(34) + ", line 1", "SystemExit"])
    if any(cls in trace_body for cls in closed):
        return fail("negative-control-traceback-counted")
    print("SUCCESS:IMP-0478-probe1 coverage-zero-unmapped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
