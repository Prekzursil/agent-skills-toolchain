#!/usr/bin/env python3
"""Named probe 1: both cache modes completed; outcomes recorded separately."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import lab as L  # noqa: E402
import schema_local as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0024-ci-image-repro.json"
SCHEMA = REPO / "command-center/schema/repro-report.schema.json"
SENTINEL = "SUCCESS:CNF-0024 emitted only when the artifact at output_path exists"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 1024:
        print("FAILED:CNF-0024-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:CNF-0024-probe1 sentinel absent")
        return 1
    if doc.get("state") != "SUCCESS" or doc.get("unit_id") != "CNF-0024":
        print("FAILED:CNF-0024-probe1 state/unit")
        return 1
    if not SCHEMA.is_file():
        print("FAILED:CNF-0024-probe1 schema missing")
        return 1

    errs = S.iter_errors(doc)
    if errs:
        print("FAILED:CNF-0024-probe1 schema", errs[0].message)
        return 1

    live = L.execute_lab()
    bad = L.assert_invariants(live)
    if bad:
        print("FAILED:CNF-0024-probe1 live lab", bad)
        return 1

    payload = S.payload_of(doc)
    for key in ("warm_cache_run", "cold_cache_run"):
        rec = payload.get(key) or {}
        if rec.get("completed") is not True:
            print(f"FAILED:CNF-0024-probe1 {key} not completed")
            return 1
        live_rec = live[key]
        if rec.get("mode") != live_rec["mode"]:
            print(f"FAILED:CNF-0024-probe1 {key} mode drift")
            return 1
        art_map = {r["id"]: r["outcome"] for r in rec.get("defect_outcomes") or []}
        live_map = {r["id"]: r["outcome"] for r in live_rec["defect_outcomes"]}
        if art_map != live_map:
            print("FAILED:CNF-0024-probe1 outcome drift", key, art_map, live_map)
            return 1

    by = {d["id"]: d for d in payload.get("defects") or []}
    cache = by.get("D-CACHE")
    if not cache:
        print("FAILED:CNF-0024-probe1 D-CACHE missing")
        return 1
    if cache["warm_cache"]["outcome"] != "FAIL" or cache["cold_cache"]["outcome"] != "PASS":
        print("FAILED:CNF-0024-probe1 D-CACHE warm/cold")
        return 1
    if not cache.get("outcome_differs"):
        print("FAILED:CNF-0024-probe1 D-CACHE did not differ")
        return 1
    for d in payload["defects"]:
        if d["warm_cache"].get("completed") is not True or d["cold_cache"].get("completed") is not True:
            print("FAILED:CNF-0024-probe1 defect cache not completed", d["id"])
            return 1

    print(json.dumps({
        "probe": "probe1-warm-cold",
        "unit_id": "CNF-0024",
        "warm_completed": True,
        "cold_completed": True,
        "d_cache_differs": True,
        "live_matches_artifact": True,
    }, sort_keys=True))
    print("SUCCESS:CNF-0024-probe1 warm and cold cache runs completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
