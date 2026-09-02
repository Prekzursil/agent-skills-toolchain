#!/usr/bin/env python3
"""Probe 1: four-cell truth table (monitor alive/dead × work active/idle).

Each cell is a live pair of independent streams (heartbeat JSONL + work
byte-growth). Production must emit four distinct verdicts and must not guess.
The receipt's published table must match this live re-run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from monitor_states import (  # noqa: E402
    CELL_ALIVE_ACTIVE,
    CELL_ALIVE_IDLE,
    CELL_DEAD_ACTIVE,
    CELL_DEAD_IDLE,
    EXPECTED_VERDICT,
    HEALTHY,
    NO_CHANGE_MONITOR,
    STALE_MONITOR,
    UNDECIDABLE,
    four_cell_live,
)

ART = REPO / "command-center" / "receipts" / "IMP-0451.json"
SENTINEL = "SENTINEL:IMP-0451:MONITOR-STATES-DISTINGUISHED"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0451-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0451":
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    table = four_cell_live()
    print(json.dumps(table["verdicts"], sort_keys=True))
    print(
        "four_distinct={0} all_match={1} any_guess={2}".format(
            table["four_distinct"], table["all_match"], table["any_guess"]
        )
    )
    if not table["all_match"]:
        return fail(f"cell mismatch {table['verdicts']}")
    if not table["four_distinct"]:
        return fail("verdicts not four-distinct")
    if table["any_guess"]:
        return fail("detector guessed")
    want = {
        CELL_ALIVE_ACTIVE: HEALTHY,
        CELL_ALIVE_IDLE: NO_CHANGE_MONITOR,
        CELL_DEAD_ACTIVE: STALE_MONITOR,
        CELL_DEAD_IDLE: UNDECIDABLE,
    }
    if table["verdicts"] != want:
        return fail(f"verdicts={table['verdicts']} want={want}")

    published = doc.get("truth_table") or {}
    pub_verdicts = published.get("verdicts") or {}
    if pub_verdicts != table["verdicts"]:
        return fail(f"receipt truth_table drifted live={table['verdicts']} art={pub_verdicts}")
    if published.get("four_distinct") is not True:
        return fail("receipt four_distinct not true")
    for name, expected in EXPECTED_VERDICT.items():
        row = next((r for r in (published.get("rows") or []) if r.get("cell") == name), None)
        if not row:
            return fail(f"receipt missing cell {name}")
        if row.get("verdict") != expected:
            return fail(f"receipt cell {name} verdict={row.get('verdict')}")
        if row.get("guessed") is True:
            return fail(f"receipt cell {name} guessed")

    print("SUCCESS:IMP-0451-probe1 four-cell-truth-table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
