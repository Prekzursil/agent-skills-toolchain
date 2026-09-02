#!/usr/bin/env python3
"""Probe 1: re-run TF-IDF measurement from the frozen gold set (not a stored-number echo)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import OUTPUT_PATH, SENTINEL, UNIT_ID  # noqa: E402
from measure import run_measurement  # noqa: E402


def main() -> int:
    if not OUTPUT_PATH.is_file():
        print("FAILED:RES-0101-probe1 artifact missing")
        return 1
    art = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    if art.get("unit_id") != UNIT_ID:
        print("FAILED:RES-0101-probe1 unit_id", art.get("unit_id"))
        return 1
    text = OUTPUT_PATH.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:RES-0101-probe1 sentinel absent")
        return 1
    if art.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0101-probe1 self-declared", art.get("state"))
        return 1

    live = run_measurement()
    live_table = live["primary"]["accuracy_versus_catalog_size"]
    art_table = art.get("accuracy_versus_catalog_size") or []
    if len(live_table) < 3 or len(art_table) < 3:
        print("FAILED:RES-0101-probe1 need >=3 sizes")
        return 1
    if live["gold_sha256"] != art.get("gold_sha256"):
        print("FAILED:RES-0101-probe1 gold sha mismatch")
        return 1
    if not live["primary"]["control_ok_every_size"]:
        print("FAILED:RES-0101-probe1 control failed on remeasure")
        return 1
    if not art.get("gold_task_set_attached") or not isinstance(art.get("gold_task_set"), dict):
        print("FAILED:RES-0101-probe1 gold task set not attached")
        return 1
    n_gold = len((art.get("gold_task_set") or {}).get("tasks") or [])
    if n_gold < 8:
        print("FAILED:RES-0101-probe1 attached gold too small", n_gold)
        return 1

    mismatches = []
    for live_row, art_row in zip(live_table, art_table):
        if live_row["catalog_size"] != art_row.get("catalog_size"):
            mismatches.append(("size", live_row["catalog_size"], art_row.get("catalog_size")))
        if live_row["correct"] != art_row.get("correct"):
            mismatches.append(("correct", live_row["correct"], art_row.get("correct")))
        if abs(float(live_row["accuracy"]) - float(art_row.get("accuracy"))) > 1e-9:
            mismatches.append(("accuracy", live_row["accuracy"], art_row.get("accuracy")))
        if not art_row.get("control_ok"):
            mismatches.append(("control_ok", True, art_row.get("control_ok")))
    if mismatches:
        print("FAILED:RES-0101-probe1 table mismatch", mismatches)
        return 1

    sizes = [r["catalog_size"] for r in live_table]
    print(
        json.dumps(
            {
                "probe": "probe1-remeasure-tfidf",
                "unit_id": UNIT_ID,
                "gold_sha256": live["gold_sha256"],
                "sizes": sizes,
                "accuracy": [r["accuracy"] for r in live_table],
                "control_ok_every_size": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:RES-0101-probe1 remeasure sizes={sizes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
