#!/usr/bin/env python3
"""Probe 1: per-study flip-rate table, distinct metric definitions, effect+baseline.

Catalog tests_required: record the flip-rate metric definition used by each study,
since they differ. Live check against the on-disk research artifact, not a fixture.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from check import (  # noqa: E402
    ART,
    CATALOG_SENTINEL,
    NOT_DELIVERING,
    distinct_metric_definitions,
    flip_rows,
    load_artifact,
    promoted_mechanisms,
    promotable,
    required_fields_ok,
    text_of,
)


def main() -> int:
    doc = load_artifact()
    blob = text_of(doc)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:RES-0081-probe1 self-declared {st}")
        return 1
    if "SUCCESS:RES-0081" not in blob:
        print("FAILED:RES-0081-probe1 SUCCESS:RES-0081 absent")
        return 1
    if CATALOG_SENTINEL not in blob:
        print("FAILED:RES-0081-probe1 catalog sentinel absent")
        return 1
    if doc.get("unit_id") != "RES-0081":
        print("FAILED:RES-0081-probe1 unit_id", doc.get("unit_id"))
        return 1

    rows = flip_rows(doc)
    if len(rows) < 4:
        print(f"FAILED:RES-0081-probe1 table too small n={len(rows)}")
        return 1

    gaps = []
    for row in rows:
        miss = required_fields_ok(row)
        if miss:
            gaps.append((row.get("study_id"), miss))
        if not promotable(row) and row.get("promoted") is True:
            gaps.append((row.get("study_id"), ["promoted-without-baseline"]))
    if gaps:
        print("FAILED:RES-0081-probe1 incomplete rows", json.dumps(gaps, default=str)[:1500])
        return 1

    defs = distinct_metric_definitions(rows)
    if len(defs) < 3:
        print(f"FAILED:RES-0081-probe1 metric definitions collapsed n={len(defs)}")
        return 1

    # Metrics must actually differ in the quantity named, not just wording.
    hay = " | ".join(sorted(defs)).lower()
    families = 0
    if "user" in hay and "view" in hay:
        families += 1
    if "are you sure" in hay or "initial answer" in hay or "%flip" in hay:
        families += 1
    if "accuracy" in hay or "acc_init" in hay:
        families += 1
    if "agree" in hay and "addition" in hay:
        families += 1
    if families < 3:
        print(f"FAILED:RES-0081-probe1 metric families too similar families={families}")
        return 1

    promoted = promoted_mechanisms(doc)
    if len(promoted) < 3:
        print(f"FAILED:RES-0081-probe1 promoted mechanisms {len(promoted)}")
        return 1
    for m in promoted:
        loc = str(m.get("locator") or "")
        src = str(m.get("arxiv_id") or m.get("doi") or "")
        if not loc or not src:
            print(f"FAILED:RES-0081-probe1 mechanism {m.get('id')} missing locator/source")
            return 1

    if str(doc.get("pooled_flip_rate") or "").upper() not in {
        "NOT-ESTABLISHED",
        "INCOMMENSURABLE",
    }:
        print("FAILED:RES-0081-probe1 illegal pooled flip-rate", doc.get("pooled_flip_rate"))
        return 1

    print(
        json.dumps(
            {
                "studies": len(rows),
                "distinct_metric_definitions": len(defs),
                "promoted_mechanisms": [m.get("id") for m in promoted],
                "artifact": "command-center/research/RES-0081.json",
            },
            indent=1,
        )
    )
    print("SUCCESS:RES-0081-probe1 flip-rate table metric-defs-differ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
