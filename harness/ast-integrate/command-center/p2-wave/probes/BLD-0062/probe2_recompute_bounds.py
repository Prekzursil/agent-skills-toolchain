#!/usr/bin/env python3
"""Probe 2: independent reviewer recomputes two bounds from raw N,n.

Does not import the author product/binary-search engine. Uses bounds_reviewer
(lgamma + linear scan) and requires defective_count_upper to match the receipt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import bounds_reviewer as BR  # noqa: E402

RECEIPT = REPO / "command-center/receipts/BLD-0062.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0062-probe2 {msg}")
    return 1


def receipt_entries(doc: dict) -> list:
    if isinstance(doc.get("entries"), list) and doc["entries"]:
        return doc["entries"]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    rows = report.get("entries")
    return rows if isinstance(rows, list) else []


def main() -> int:
    if not RECEIPT.is_file():
        return fail("receipt missing")
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in receipt_entries(doc) if isinstance(e, dict)}
    pairs = [
        ("phase0-ci-28-of-60", 60, 28),
        ("FIXTURE-convenience-as-stratified", 100, 8),
    ]
    for eid, n_pop, n_samp in pairs:
        row = by_id.get(eid)
        if not row:
            return fail(f"missing {eid}")
        recorded = row.get("missed_defect_bound_95") or {}
        recomputed = BR.missed_defect_bound_95(n_pop, n_samp)
        print(
            f"{eid} recorded_k={recorded.get('defective_count_upper')} "
            f"recorded_rate={recorded.get('rate')} "
            f"reviewer_k={recomputed.get('defective_count_upper')} "
            f"reviewer_rate={recomputed.get('rate')} "
            f"match={BR.bounds_match(recorded, recomputed)}"
        )
        if recorded.get("population") not in (n_pop, None) and recorded.get(
            "status"
        ) == "COMPUTED":
            if int(recorded["population"]) != n_pop:
                return fail(f"{eid} population drift")
        if not BR.bounds_match(recorded, recomputed):
            return fail(f"{eid} reviewer disagreement")

    unk = by_id.get("FIXTURE-unknown-population") or {}
    unk_rec = unk.get("missed_defect_bound_95") or {}
    unk_rev = BR.missed_defect_bound_95(None, 12)
    print(f"unknown recorded={unk_rec.get('status')} reviewer={unk_rev.get('status')}")
    if unk_rec.get("status") != BR.NOT_COMPUTABLE:
        return fail("unknown recorded status")
    if unk_rev.get("status") != BR.NOT_COMPUTABLE:
        return fail("reviewer computed a rate for unknown N")
    if "rate" in unk_rev:
        return fail("reviewer leaked rate on unknown N")

    census = by_id.get("FIXTURE-census") or {}
    census_rev = BR.missed_defect_bound_95(10, 10)
    if not BR.bounds_match(census.get("missed_defect_bound_95") or {}, census_rev):
        return fail("census reviewer disagreement")
    if census_rev.get("rate") != 0:
        return fail("census reviewer rate not 0")

    print("SUCCESS:BLD-0062-probe2 independent bound recompute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
