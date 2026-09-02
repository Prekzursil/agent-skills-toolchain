#!/usr/bin/env python3
"""Probe 2: mechanically different re-probe of each inventoried assertion.

Known-stale calibrations must come back REFUTED. Confirming either means this
sweep re-ran the original probe. Same-instrument greps are NOT-CHECKED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import UNIT, probe2_payload  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def by_id(payload: dict, aid: str) -> dict:
    for row in payload["assertions"]:
        if row["id"] == aid:
            return row
    return {}


def main() -> int:
    payload = probe2_payload()
    print(json.dumps(payload, sort_keys=True, default=str))
    mnn = by_id(payload, "CAL-MNN-STILL-LIVE")
    retired = by_id(payload, "CAL-RETIRED-TOOL-AVAILABLE")
    catalog = by_id(payload, "CTRL-CATALOG-PARSES")
    zero = by_id(payload, "GROUND-ZERO-SUCCESS")
    same = by_id(payload, "SAME-INSTRUMENT-MNN")
    if mnn.get("verdict") != "REFUTED":
        return fail(f"known-stale M-NN must be REFUTED, got {mnn.get('verdict')}")
    if retired.get("verdict") != "REFUTED":
        return fail(f"known-stale retired tool must be REFUTED, got {retired.get('verdict')}")
    if catalog.get("verdict") != "CONFIRMED":
        return fail(f"true catalog control must be CONFIRMED, got {catalog.get('verdict')}")
    if zero.get("verdict") != "REFUTED":
        return fail(f"zero-SUCCESS pin must be REFUTED, got {zero.get('verdict')}")
    if same.get("verdict") != "NOT-CHECKED":
        return fail(f"same-instrument row must be NOT-CHECKED, got {same.get('verdict')}")
    ctrl = payload["controls"]
    if not ctrl["fixture_overlap_is_one"]:
        return fail("id-intersection counter did not see the planted one-id overlap")
    if not ctrl["disjoint_overlap_is_zero"]:
        return fail("id-intersection counter was not silent on the disjoint pair")
    if not ctrl["naive_grep_would_confirm_stale_mnn"]:
        return fail("naive original grep did not even see the 31-way phrase")
    if not payload["pass"]:
        return fail("reprobe conjunction failed")
    print(
        f"mnn={mnn['verdict']} retired={retired['verdict']} "
        f"catalog={catalog['verdict']} zero_success={zero['verdict']} "
        f"same={same['verdict']}"
    )
    print("SUCCESS:ADV-0012-probe2 reprobe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
