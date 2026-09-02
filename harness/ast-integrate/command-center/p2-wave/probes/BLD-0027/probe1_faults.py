#!/usr/bin/env python3
"""Probe 1: executed catalog faults + planted mtime-only control + live adapter."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402
import live_adapters as L  # noqa: E402
import scenarios as S  # noqa: E402

RECEIPT = HERE.parents[3] / "command-center" / "receipts" / "BLD-0027.json"


def main() -> int:
    faults = S.run_catalog_faults()
    live = L.run_live_adapter_faults()
    inv = I.inventory()
    failed = [r["id"] for r in faults["rows"] if not r.get("pass")]
    print(json.dumps({"failed": failed, "live": live, "required_missing": inv["required_missing"]}, sort_keys=True))
    if failed:
        print(f"FAILED:BLD-0027-probe1 catalog faults {failed}")
        return 1
    if not faults.get("naive_timeout_caught") or not faults.get("naive_11h_caught"):
        print("FAILED:BLD-0027-probe1 planted mtime-only classifier not caught")
        return 1
    if not live.get("timeout_not_success") or not live.get("missing_not_success"):
        print("FAILED:BLD-0027-probe1 live adapter SUCCESS on timeout/missing")
        return 1
    if RECEIPT.is_file():
        text = RECEIPT.read_text(encoding="utf-8")
        if "SUCCESS:BLD-0027" not in text:
            print("FAILED:BLD-0027-probe1 receipt sentinel absent")
            return 1
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:BLD-0027-probe1 receipt state={doc.get('state')}")
            return 1
    print(
        "catalog_pass=True naive_timeout={0} naive_11h={1} timeout_state={2} missing_state={3} surfaces_missing={4}".format(
            faults.get("naive_timeout_caught"),
            faults.get("naive_11h_caught"),
            live["timeout"]["state"],
            live["exit0_missing"]["state"],
            inv["required_missing"],
        )
    )
    print("SUCCESS:BLD-0027-probe1 executed catalog faults and planted mtime control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
