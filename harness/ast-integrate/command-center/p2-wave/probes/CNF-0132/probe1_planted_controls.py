#!/usr/bin/env python3
"""Probe 1: planted controls required by the CNF-0132 catalog row.

Different instrument from probe 2: executes union-find rank on the planted
fixture file (not the receipt edge list).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import evaluate_required_tests  # noqa: E402
from ingest import load_planted  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0132.json"


def main() -> int:
    records = list(load_planted().get("records") or [])
    tests = evaluate_required_tests(records)
    printable = [
        {"id": t["id"], "result": t["result"], "detail": t.get("detail")} for t in tests
    ]
    print(json.dumps(printable, sort_keys=True))
    failed = [t for t in tests if t.get("result") != "PASS"]
    if failed:
        print("FAILED:CNF-0132-probe1 planted controls")
        return 1
    if not ART.is_file():
        print("FAILED:CNF-0132-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:CNF-0132-probe1 self-declared {doc.get('state')}")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNF-0132" not in text:
        print("FAILED:CNF-0132-probe1 sentinel absent")
        return 1
    art_tests = {t.get("id"): t.get("result") for t in (doc.get("tests") or [])}
    for t in tests:
        if art_tests.get(t["id"]) != "PASS":
            print(f"FAILED:CNF-0132-probe1 receipt test {t['id']} not PASS")
            return 1
    rank1 = doc.get("rank1_collapses") or []
    if not any(r.get("claim_id") == "C-CACHE-COLLAPSE" for r in rank1):
        print("FAILED:CNF-0132-probe1 rank-1 collapse C-CACHE-COLLAPSE not named")
        return 1
    shared = []
    for row in rank1:
        if row.get("claim_id") == "C-CACHE-COLLAPSE":
            shared.extend(row.get("shared_upstreams") or [])
    if "cache://shared-blob-9f3c" not in shared:
        print(f"FAILED:CNF-0132-probe1 missing shared upstream cite: {shared}")
        return 1
    print("SUCCESS:CNF-0132-probe1 planted controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
