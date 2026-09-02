#!/usr/bin/env python3
"""Probe 1: re-run interleaved import-time measurement; require both commit tables."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from measure import run_campaign, write_raw  # noqa: E402
from scenario import AFTER_ID, BEFORE_ID, CATALOG_SENTINEL, OUT_REL, REPO  # noqa: E402
from schemautil import payload  # noqa: E402

RAW = HERE / "probe1-interleaved.raw.json"


def main() -> int:
    art = REPO / OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        print("FAILED:CNF-0053-probe1 artifact missing")
        return 1
    text = art.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0053":
        print("FAILED:CNF-0053-probe1 unit_id", doc.get("unit_id"))
        return 1
    if CATALOG_SENTINEL not in text:
        print("FAILED:CNF-0053-probe1 catalog sentinel absent")
        return 1
    body = payload(doc)
    table = body.get("per_module_cost_table") or {}
    if BEFORE_ID not in table or AFTER_ID not in table:
        print("FAILED:CNF-0053-probe1 per-module table missing a commit")
        return 1
    if not table[BEFORE_ID] or not table[AFTER_ID]:
        print("FAILED:CNF-0053-probe1 empty per-module table")
        return 1

    live = run_campaign()
    write_raw(
        {
            "delta_ms": live["delta_ms"],
            "noise_floor_ms": live["noise_floor_ms"],
            "after_slower": live["after_slower"],
            "largest": live["largest_increase_module"],
            "table_keys": sorted(live["per_module_cost_table"]),
            "raw_n": len(live["raw_repetitions"]),
        },
        RAW,
    )
    if live["largest_increase_module"]["module"] != "tool_startup.extra":
        print(
            "FAILED:CNF-0053-probe1 live largest "
            f"{live['largest_increase_module']}"
        )
        return 1
    if not live["after_slower"]:
        print(
            "FAILED:CNF-0053-probe1 live after not slower "
            f"delta={live['delta_ms']} noise={live['noise_floor_ms']}"
        )
        return 1
    if len(live["raw_repetitions"]) < 22:
        print("FAILED:CNF-0053-probe1 under-sampled", len(live["raw_repetitions"]))
        return 1
    orders = [r["commit_id"] for r in live["raw_repetitions"][:4]]
    if orders != [BEFORE_ID, AFTER_ID, BEFORE_ID, AFTER_ID]:
        print("FAILED:CNF-0053-probe1 not interleaved A B A B", orders)
        return 1
    art_largest = (body.get("largest_increase_module") or {}).get("module")
    if art_largest != "tool_startup.extra":
        print("FAILED:CNF-0053-probe1 artifact largest", art_largest)
        return 1

    print(
        f"interleaved n={len(live['raw_repetitions'])} "
        f"delta_ms={live['delta_ms']} noise={live['noise_floor_ms']} "
        f"largest={live['largest_increase_module']['module']}"
    )
    print("SUCCESS:CNF-0053-probe1 interleaved importtime both-commit tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
