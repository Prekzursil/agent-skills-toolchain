#!/usr/bin/env python3
"""Probe 1: all twelve 6x2 cells populated; true FIRE; false SILENT."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import table as T  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0121-stopping-rule-both-states-simulation-across-all-six-requir.md"
)
SENTINEL = "SUCCESS:CNL-0121"


def main() -> int:
    result = T.run_table()
    print(json.dumps(
        {
            "probe": "probe1-six-by-two",
            "cell_count": result["cell_count"],
            "populated_cells": result["populated_cells"],
            "unpopulated_cells": result["unpopulated_cells"],
            "fire_on_true": result["fire_on_true"],
            "silent_on_false": result["silent_on_false"],
            "failed": len(result["failed"]),
            "not_checked": len(result["not_checked"]),
        },
        sort_keys=True,
    ))
    for cell in result["cells"]:
        print(cell["verbatim"])

    if result["cell_count"] != 12:
        print(f"FAILED:CNL-0121-probe1 cell_count={result['cell_count']} want=12")
        return 1
    if result["populated_cells"] != 12 or result["unpopulated_cells"] != 0:
        print("FAILED:CNL-0121-probe1 unpopulated cell is NOT-CHECKED")
        return 1
    if result["fire_on_true"] != 6:
        print(f"FAILED:CNL-0121-probe1 fire_on_true={result['fire_on_true']} want=6")
        return 1
    if result["silent_on_false"] != 6:
        print(f"FAILED:CNL-0121-probe1 silent_on_false={result['silent_on_false']} want=6")
        return 1
    if result["failed"] or result["not_checked"]:
        print("FAILED:CNL-0121-probe1 failed or NOT-CHECKED cells")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0121-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNL-0121-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0121-probe1 self-declared {doc.get('state')}")
        return 1
    rows = (doc.get("outcome_table") or {}).get("rows") or []
    if len(rows) != 6:
        print(f"FAILED:CNL-0121-probe1 artifact rows={len(rows)} want=6")
        return 1
    live = {}
    for r in result["rows"]:
        live[(r["expression_id"], "true")] = r["true_state"]["observed"]
        live[(r["expression_id"], "false")] = r["false_state"]["observed"]
    for r in rows:
        eid = r["expression_id"]
        for state, key in (("true", "true_state"), ("false", "false_state")):
            art_obs = r[key]["observed"]
            if live[(eid, state)] != art_obs:
                print(f"FAILED:CNL-0121-probe1 artifact mismatch {eid} {state}")
                return 1
            if not r[key].get("verbatim"):
                print(f"FAILED:CNL-0121-probe1 empty verbatim {eid} {state}")
                return 1
    print("SUCCESS:CNL-0121-probe1 6x2 table populated FIRE/SILENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
