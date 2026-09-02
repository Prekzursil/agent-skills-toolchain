#!/usr/bin/env python3
"""Probe 1: implementer-right, confirmer-right, and IRREDUCIBLE are all live."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from campaign import run_campaign  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "CNF-0135.json"
SENTINEL = "SUCCESS:CNF-0135"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0135-probe1 {msg}")
    return 1


def main() -> int:
    camp = run_campaign()
    by_id = {e["id"]: e for e in camp["entries"]}
    d1, d2, d3 = by_id["D-001"], by_id["D-002"], by_id["D-003"]
    if d1["status"] != "CLOSED_CONFIRMER_REVISED":
        return fail(f"live D-001 {d1['status']}")
    if d2["status"] != "CLOSED_IMPLEMENTER_REVISED":
        return fail(f"live D-002 {d2['status']}")
    if d3["status"] != "IRREDUCIBLE":
        return fail(f"live D-003 {d3['status']}")
    if d1["preregistered_at"] >= d1["run_at"] or d2["preregistered_at"] >= d2["run_at"]:
        return fail("live pre-registration did not precede run")
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    rec = {e["id"]: e for e in doc.get("entries") or []}
    if rec.get("D-001", {}).get("status") != "CLOSED_CONFIRMER_REVISED":
        return fail("receipt D-001")
    if rec.get("D-002", {}).get("status") != "CLOSED_IMPLEMENTER_REVISED":
        return fail("receipt D-002")
    if rec.get("D-003", {}).get("status") != "IRREDUCIBLE":
        return fail("receipt D-003")
    for eid in ("D-001", "D-002"):
        row = rec[eid]
        if not row.get("test_id") or not row.get("preregistered_at") or not row.get("verbatim_result"):
            return fail(f"receipt {eid} missing test evidence")
        if row["preregistered_at"] >= row["run_at"]:
            return fail(f"receipt {eid} test did not predate close")
    print(json.dumps({
        "probe": "probe1-both-sides-and-irreducible",
        "unit_id": "CNF-0135",
        "live_d1": d1["status"],
        "live_d2": d2["status"],
        "live_d3": d3["status"],
        "receipt_replayed": True,
        "pass": True,
    }, sort_keys=True))
    print("SUCCESS:CNF-0135-probe1 both-sides revise and irreducible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
