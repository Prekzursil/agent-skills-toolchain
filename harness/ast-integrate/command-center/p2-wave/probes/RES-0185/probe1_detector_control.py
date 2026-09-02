#!/usr/bin/env python3
"""Probe 1: detector control — planted single-source vs four-class vs empty lineage.

Re-scores the plants from plants.py (not from stored labels) and checks the
artifact map agrees. A mapper silent on both plants is measuring nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from mapper import score  # noqa: E402
from plants import (  # noqa: E402
    PLANT_FOUR_ID,
    PLANT_SINGLE_ID,
    PLANT_UNSUPPORTED_ID,
    plants,
)

ART = REPO / (
    "command-center/research/evidence-quality/"
    "RES-0185-evidence-map-coverage-holes.json"
)
SENTINEL = "SUCCESS:RES-0185"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0185-probe1 {msg}")
    return 1


def main() -> int:
    live = {p["id"]: score(p["lineage_records"]) for p in plants()}
    s = live[PLANT_SINGLE_ID]
    f = live[PLANT_FOUR_ID]
    u = live[PLANT_UNSUPPORTED_ID]
    payload = {
        "probe": "probe1-detector-control",
        "single_source_status": s["support_status"],
        "single_source_flag": s["single_source"],
        "four_class_status": f["support_status"],
        "four_class_single_source": f["single_source"],
        "four_class_count": f["class_count"],
        "unsupported_status": u["support_status"],
        "both_states": bool(s["single_source"] and not f["single_source"]),
    }
    print(json.dumps(payload, sort_keys=True))
    if not s["single_source"] or s["support_status"] != "SINGLE-SOURCE":
        return fail("single-source plant not marked single-source")
    if f["single_source"]:
        return fail("four-class plant marked single-source")
    if f["class_count"] < 4:
        return fail(f"four-class plant class_count={f['class_count']}")
    if u["support_status"] != "UNSUPPORTED":
        return fail("empty-lineage plant not UNSUPPORTED")
    if s["single_source"] == f["single_source"]:
        return fail("detector silent: both plants share single_source flag")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {exc}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared:{st}")
    by_id = {
        c["id"]: c
        for c in (doc.get("conclusions") or [])
        if isinstance(c, dict)
    }
    for pid, expect_single, expect_status in (
        (PLANT_SINGLE_ID, True, "SINGLE-SOURCE"),
        (PLANT_FOUR_ID, False, None),
        (PLANT_UNSUPPORTED_ID, False, "UNSUPPORTED"),
    ):
        row = by_id.get(pid)
        if row is None:
            return fail(f"plant {pid} omitted from map")
        if bool(row.get("single_source")) != expect_single:
            return fail(f"artifact {pid} single_source={row.get('single_source')}")
        if expect_status and row.get("support_status") != expect_status:
            return fail(f"artifact {pid} status={row.get('support_status')}")
    if not doc.get("unsupported_shown_not_omitted"):
        return fail("unsupported_shown_not_omitted is not true")
    print(
        "DETECTOR CONTROL: single-source plant marked SINGLE-SOURCE; "
        "four-class plant not single-source; empty lineage UNSUPPORTED on map."
    )
    print("SUCCESS:RES-0185-probe1 detector-control plants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
