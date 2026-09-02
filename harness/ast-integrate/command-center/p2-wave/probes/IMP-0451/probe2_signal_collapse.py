#!/usr/bin/env python3
"""Probe 2: collapsing two signals into one makes mixed cells indistinguishable.

Production keeps NO_CHANGE_MONITOR (11316) distinct from STALE_MONITOR (11315).
OR-collapse and AND-collapse both map those two cells to the same bit, so the
four-cell distinctness test goes red — proving the pair is not a single signal
in disguise.

Hardest cell (adversarial): dead×idle must be UNDECIDABLE, not a guess copied
from either mixed neighbour. mtime-only observations are UNDECIDABLE.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from monitor_states import (  # noqa: E402
    CELL_ALIVE_IDLE,
    CELL_DEAD_ACTIVE,
    CELL_DEAD_IDLE,
    UNDECIDABLE,
    four_cell_live,
    four_verdicts_distinct,
    hardest_cell_undecidable,
)

ART = REPO / "command-center" / "receipts" / "IMP-0451.json"
SENTINEL = "SENTINEL:IMP-0451:MONITOR-STATES-DISTINGUISHED"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0451-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    table = four_cell_live()
    hard = hardest_cell_undecidable(table)
    print("collapsed_or", json.dumps(table["collapsed_or"], sort_keys=True))
    print("collapsed_and", json.dumps(table["collapsed_and"], sort_keys=True))
    print(
        "or_mixed={0} and_mixed={1} production_mixed={2} four_distinct={3}".format(
            table["or_mixed_indistinguishable"],
            table["and_mixed_indistinguishable"],
            table["production_mixed_indistinguishable"],
            table["four_distinct"],
        )
    )
    print(
        "hardest verdict={0} guessed={1} pass={2}".format(
            hard["verdict"], hard["guessed"], hard["pass"]
        )
    )

    if not table["four_distinct"]:
        return fail("production cells not distinct")
    if table["production_mixed_indistinguishable"]:
        return fail("production mixed cells already collapsed")
    if not table["or_mixed_indistinguishable"]:
        return fail("OR mutant did not collapse 11315/11316 cells")
    if not table["and_mixed_indistinguishable"]:
        return fail("AND mutant did not collapse 11315/11316 cells")
    if four_verdicts_distinct(table["collapsed_or"]):
        return fail("OR mutant still four-distinct (mutant did not go red)")
    if four_verdicts_distinct(table["collapsed_and"]):
        return fail("AND mutant still four-distinct (mutant did not go red)")
    if table["collapsed_or"][CELL_ALIVE_IDLE] != table["collapsed_or"][CELL_DEAD_ACTIVE]:
        return fail("OR mutant mixed cells still differ")
    if not table["idle_read_as_dead"]:
        return fail("silence-is-dead mutant did not fire on alive-idle")
    if not table["dead_read_as_idle"]:
        return fail("any-activity-is-alive mutant did not fire on dead-active")
    if not table["mtime_forbidden_undecidable"]:
        return fail("mtime observation was not UNDECIDABLE")
    if table["mtime_control"].get("guessed") is True:
        return fail("mtime path guessed")
    if not hard["pass"]:
        return fail(f"hardest cell {hard}")
    if hard["verdict"] != UNDECIDABLE or hard["guessed"]:
        return fail("hardest cell guessed instead of UNDECIDABLE")
    if hard["inherited_no_change_verdict"] or hard["inherited_stale_verdict"]:
        return fail("hardest cell inherited a mixed-cell verdict")

    mut = doc.get("mutation") or {}
    if mut.get("or_mixed_indistinguishable") is not True:
        return fail("receipt missing OR mixed-indistinguishable")
    if mut.get("and_mixed_indistinguishable") is not True:
        return fail("receipt missing AND mixed-indistinguishable")
    if mut.get("four_cell_goes_red") is not True:
        return fail("receipt mutation four_cell_goes_red not true")
    art_hard = doc.get("hardest_cell") or {}
    if art_hard.get("verdict") != UNDECIDABLE:
        return fail(f"receipt hardest_cell {art_hard.get('verdict')}")
    if art_hard.get("cell") != CELL_DEAD_IDLE:
        return fail("receipt hardest_cell is not dead-idle")

    print("mutant_goes_red=true namespacing_deleted_goes_red analogue: signal-collapse")
    print("SUCCESS:IMP-0451-probe2 signal-collapse-and-hardest-cell")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
