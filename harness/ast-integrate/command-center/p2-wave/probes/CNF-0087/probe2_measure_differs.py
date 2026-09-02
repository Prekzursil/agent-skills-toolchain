#!/usr/bin/env python3
"""Probe 2: independent recount is not the council measure re-run.

Council string-identity and mechanism-key must disagree on the planted
subset (4 vs 1). Re-running the council measure twice still yields 4,
so identity of outcome is not what proves independence — the mechanical
family and the plant discrimination are.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from ledger import PLANTED, SEED_ID, build_ledger  # noqa: E402
from measures import (  # noqa: E402
    COUNCIL_MEASURE,
    RECOUNT_MEASURE,
    council_unique,
    recount_unique,
    report_payload,
)

ART = REPO / "command-center/confirmation/CNF-0087-idea-count-recount.json"


def main() -> int:
    if COUNCIL_MEASURE["mechanical_family"] == RECOUNT_MEASURE["mechanical_family"]:
        print("FAILED:CNF-0087-probe2 same mechanical family")
        return 1
    if COUNCIL_MEASURE["id"] == RECOUNT_MEASURE["id"]:
        print("FAILED:CNF-0087-probe2 same measure id")
        return 1
    ledger = build_ledger()
    ideas = ledger["ideas"]
    planted_ids = {SEED_ID, *[p[0] for p in PLANTED]}
    plant = [i for i in ideas if i["id"] in planted_ids]
    c1 = council_unique([i["text"] for i in plant])
    c2 = council_unique([i["text"] for i in plant])
    r1 = recount_unique(plant)
    if c1 != 4 or c2 != 4:
        print(f"FAILED:CNF-0087-probe2 council plant unique c1={c1} c2={c2} want=4")
        return 1
    if r1 != 1:
        print(f"FAILED:CNF-0087-probe2 recount plant unique={r1} want=1")
        return 1
    if c1 == r1:
        print("FAILED:CNF-0087-probe2 measures agree on the plant (same-measure-rerun shape)")
        return 1
    full_c = council_unique([i["text"] for i in ideas])
    full_r = recount_unique(ideas)
    if full_c == full_r:
        print("FAILED:CNF-0087-probe2 full-ledger counts identical")
        return 1
    if not ART.is_file():
        print("FAILED:CNF-0087-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    body = report_payload(doc)
    families = {
        m.get("mechanical_family")
        for m in (body.get("measures") or [])
        if isinstance(m, dict)
    }
    if len(families) < 2:
        print(f"FAILED:CNF-0087-probe2 artifact measure families {families}")
        return 1
    tv = body.get("target_verdict") or {}
    if tv.get("survives") is True:
        print("FAILED:CNF-0087-probe2 artifact claims target survives after collapse")
        return 1
    if tv.get("classification") != "target-not-met":
        print(f"FAILED:CNF-0087-probe2 classification={tv.get('classification')}")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe2-measure-differs",
                "unit_id": "CNF-0087",
                "council_family": COUNCIL_MEASURE["mechanical_family"],
                "recount_family": RECOUNT_MEASURE["mechanical_family"],
                "council_plant_unique": c1,
                "council_rerun_plant_unique": c2,
                "recount_plant_unique": r1,
                "full_council_unique": full_c,
                "full_recount_unique": full_r,
                "same_measure_rerun_would_stay": c1,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0087-probe2 measures differ mechanically")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
