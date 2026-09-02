#!/usr/bin/env python3
"""Probe 1: partition arithmetic + known-present control.

Rebuilds the frame from the universe, then independently sums the published
stratum table in the receipt when that file exists.

When live CLAIM-REGISTRY.json is present but unstratifiable, also prove the
frame builder fails loudly on missing severity (does not default to low and
does not silently drop those rows into a 0/0 pass).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from frame import (  # noqa: E402
    FrameBuildError,
    build_frame,
    extract_claim_list,
    locate_claim,
    recompute_table_sum,
    stratum_rows,
)
from universe import LIVE_REGISTRY, load_universe  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "CNF-0137.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0137-probe1 {msg}")
    return 1


def _published_strata(rec: dict) -> list:
    if isinstance(rec.get("strata"), list) and rec["strata"]:
        return rec["strata"]
    report = rec.get("report")
    if isinstance(report, dict) and isinstance(report.get("strata"), list):
        return report["strata"]
    return []


def _published_n(rec: dict) -> int:
    proof = rec.get("partition_proof")
    if not isinstance(proof, dict):
        report = rec.get("report")
        proof = report.get("partition_proof") if isinstance(report, dict) else {}
    try:
        return int((proof or {}).get("registry_n") or 0)
    except (TypeError, ValueError):
        return 0


def main() -> int:
    uni = load_universe()
    known_id = str(uni["known_claim_id"])
    known_key = tuple(uni["known_key"])

    if uni["live_registry_present"] and not uni["live_stratifiable"]:
        live_doc = json.loads(LIVE_REGISTRY.read_text(encoding="utf-8"))
        try:
            live_claims = extract_claim_list(live_doc)
            build_frame(live_claims, uni["catalog_vendors"])
        except FrameBuildError as exc:
            err = str(exc)
            if "severity" not in err.lower():
                return fail(f"live-unstratifiable error did not name severity: {exc}")
            if (
                "default to low" not in err.lower()
                and "refusing to default" not in err.lower()
            ):
                return fail(f"live-unstratifiable was not the loud default-refusal: {exc}")
        else:
            return fail(
                "live CLAIM-REGISTRY.json framed despite missing axes; "
                "would have defaulted or dropped the denominator"
            )

    try:
        frame = build_frame(uni["claims"], uni["catalog_vendors"])
    except FrameBuildError as exc:
        return fail(f"frame-build: {exc}")
    proof = frame.proof
    if proof["registry_n"] != proof["sum_stratum_counts"]:
        return fail("sum(stratum counts) != registry n")
    if not proof["pairwise_intersections_empty"]:
        return fail("pairwise intersections not empty")
    if not proof["every_claim_exactly_one"]:
        return fail("not every claim in exactly one stratum")
    if proof["dropped_claim_ids"]:
        return fail(f"dropped claims {proof['dropped_claim_ids']}")

    try:
        key, members = locate_claim(frame, known_id)
    except FrameBuildError as exc:
        return fail(f"known-present: {exc}")
    if key != known_key:
        return fail(f"known claim landed in {key}, predicted {known_key}")
    if members.count(known_id) != 1:
        return fail("known claim not unique in its stratum")

    published_ok = None
    if RECEIPT.is_file():
        rec = json.loads(RECEIPT.read_text(encoding="utf-8"))
        try:
            table = recompute_table_sum(_published_strata(rec))
        except FrameBuildError as exc:
            return fail(f"published-table: {exc}")
        pub_n = _published_n(rec)
        if table["sum_stratum_counts"] != pub_n:
            return fail(
                f"published sum={table['sum_stratum_counts']} != receipt registry_n={pub_n}"
            )
        if table["sum_stratum_counts"] != proof["registry_n"]:
            return fail("published table n drifted from live rebuild")
        published_ok = True

    rows = stratum_rows(frame)
    payload = {
        "pass": True,
        "probe": "probe1-partition-and-known",
        "origin": uni["origin"],
        "live_registry_present": uni["live_registry_present"],
        "live_stratifiable": uni["live_stratifiable"],
        "live_error": uni["live_error"],
        "registry_n": proof["registry_n"],
        "stratum_count": proof["stratum_count"],
        "sum_stratum_counts": proof["sum_stratum_counts"],
        "pairwise_intersections_empty": True,
        "known_claim_id": known_id,
        "known_stratum": "|".join(key),
        "known_stratum_size": len(members),
        "published_table_recomputed": published_ok,
        "stratum_ids": [r["stratum_id"] for r in rows],
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        f"n={proof['registry_n']} strata={proof['stratum_count']} "
        f"known={known_id} in {'|'.join(key)} "
        f"published_ok={published_ok}"
    )
    print("SUCCESS:CNF-0137-probe1 partition and known-present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
