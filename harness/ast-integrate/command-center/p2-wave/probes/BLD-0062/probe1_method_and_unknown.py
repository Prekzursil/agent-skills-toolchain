#!/usr/bin/env python3
"""Probe 1: method reclassification, unknown-N NOT-COMPUTABLE, corpus coverage.

Independent of the receipt's narrative: re-runs classify + bounds on fixtures,
JSON-walks the catalog, and requires every walk hit to appear in the audit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import bounds as B  # noqa: E402
import classify as C  # noqa: E402
import corpus as CX  # noqa: E402

RECEIPT = REPO / "command-center/receipts/BLD-0062.json"
SNAPSHOT = REPO / "command-center/BASELINE-SNAPSHOT.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0062-probe1 {msg}")
    return 1


def receipt_entries(doc: dict) -> list:
    if isinstance(doc.get("entries"), list) and doc["entries"]:
        return doc["entries"]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    rows = report.get("entries")
    return rows if isinstance(rows, list) else []


def receipt_coverage(doc: dict) -> dict:
    if isinstance(doc.get("corpus_coverage"), dict):
        return doc["corpus_coverage"]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    cov = report.get("corpus_coverage")
    return cov if isinstance(cov, dict) else {}


def main() -> int:
    conv = json.loads(
        (HERE / "fixtures/convenience_as_stratified.json").read_text(encoding="utf-8")
    )
    unk = json.loads(
        (HERE / "fixtures/unknown_population.json").read_text(encoding="utf-8")
    )
    census = json.loads((HERE / "fixtures/census.json").read_text(encoding="utf-8"))

    conv_m = C.classify_method(conv)
    unk_m = C.classify_method(unk)
    census_m = C.classify_method(census)
    print(f"convenience_claimed={conv.get('claimed_method')} classified={conv_m}")
    print(f"unknown_claimed={unk.get('claimed_method')} classified={unk_m}")
    print(f"census_claimed={census.get('claimed_method')} classified={census_m}")
    if conv_m != "convenience":
        return fail(f"convenience-as-stratified classified {conv_m}")
    if census_m != "census":
        return fail(f"census classified {census_m}")

    unk_b = B.missed_defect_bound_95(unk.get("population_size"), unk.get("sample_size"))
    print(f"unknown_bound={unk_b}")
    if unk_b.get("status") != B.NOT_COMPUTABLE:
        return fail("unknown population produced a confidence number")
    if "rate" in unk_b:
        return fail("unknown population bound still carries rate")
    if unk.get("planted_confidence") == 0.95 and unk_b.get("rate") == 0.95:
        return fail("planted confidence leaked into bound")

    census_b = B.missed_defect_bound_95(
        census.get("population_size"), census.get("sample_size")
    )
    if census_b.get("status") != "COMPUTED" or census_b.get("rate") != 0:
        return fail(f"census bound {census_b}")

    if not RECEIPT.is_file():
        return fail("receipt missing")
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if "SUCCESS:BLD-0062" not in RECEIPT.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    by_id = {e["id"]: e for e in receipt_entries(doc) if isinstance(e, dict)}
    for required in (
        "phase0-ci-28-of-60",
        "phase11-stratified-claim-sample",
        "AUD-0086-representative-shell-roundtrip",
        "FIXTURE-convenience-as-stratified",
        "FIXTURE-unknown-population",
    ):
        if required not in by_id:
            return fail(f"receipt missing entry {required}")
    if by_id["FIXTURE-convenience-as-stratified"].get(
        "selection_method_classified"
    ) != "convenience":
        return fail("receipt did not reclassify convenience fixture")
    if by_id["FIXTURE-unknown-population"]["missed_defect_bound_95"].get(
        "status"
    ) != B.NOT_COMPUTABLE:
        return fail("receipt unknown-pop not NOT-COMPUTABLE")
    if by_id["phase11-stratified-claim-sample"]["missed_defect_bound_95"].get(
        "status"
    ) != B.NOT_COMPUTABLE:
        return fail("phase11 bound should be NOT-COMPUTABLE")
    if by_id["phase0-ci-28-of-60"].get("selection_method_classified") != "convenience":
        return fail("phase0 should be convenience (executed-because-they-ran)")

    cov = receipt_coverage(doc)
    located_keys = {h.get("key") for h in (cov.get("hits") or []) if isinstance(h, dict)}
    walk = CX.scan_catalog_units()
    missing = []
    for h in walk:
        key = CX.coverage_key(h)
        if key not in located_keys:
            missing.append(key)
    print(f"walk_hits={len(walk)} receipt_located={len(located_keys)} missing={len(missing)}")
    if missing:
        print("missing keys:", missing[:8])
        return fail("json-walk claim not in audit located set")
    unlocated = cov.get("unlocated") or []
    unlocated_blob = " ".join(
        str(u.get("path")) for u in unlocated if isinstance(u, dict)
    )
    if SNAPSHOT.is_file():
        if "BASELINE-SNAPSHOT.json" in unlocated_blob:
            return fail("present BASELINE-SNAPSHOT.json wrongly reported unlocated")
        on_disk = by_id["phase0-ci-28-of-60"].get("on_disk") or {}
        if on_disk.get("BASELINE-SNAPSHOT.json") is not True:
            return fail("phase0 did not record live snapshot present")
    elif "BASELINE-SNAPSHOT.json" not in unlocated_blob:
        return fail("absent BASELINE-SNAPSHOT.json not reported unlocated")
    if "CNF-0003-sampling-frame.json" not in unlocated_blob:
        cnf = REPO / "command-center/confirmation/CNF-0003-sampling-frame.json"
        if not cnf.is_file():
            return fail("absent CNF-0003 sampling frame not reported unlocated")
    print(
        "reclass=convenience unknown=NOT-COMPUTABLE census_rate=0 "
        f"coverage_ok walk={len(walk)}"
    )
    print("SUCCESS:BLD-0062-probe1 method unknown-pop coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
