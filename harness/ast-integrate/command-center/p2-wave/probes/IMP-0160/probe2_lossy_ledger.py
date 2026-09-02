#!/usr/bin/env python3
"""Probe 2: inexpressible constructs land in the lossy ledger (both-states).

Good state: workflows/rtv-pdr.js — Date.now and fire-and-forget are absent
from the ledger (they are not in the source).
Bad state: planted Date.now() AND planted fire-and-forget agent() — each
appears in the ledger, and the fire-and-forget site is NOT normalised into
a blocking WorkUnit (no unit id 'ghost').
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "import-adapters"))
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.spec import FanOut  # noqa: E402
from agentspec.validate import validate_workflow  # noqa: E402
from claude_saved_workflow import import_path  # noqa: E402

UNIT = "IMP-0160"
GOOD = REPO / "workflows" / "rtv-pdr.js"
BAD_DATE = HERE / "fixtures" / "inexpressible-date-now.js"
BAD_FF = HERE / "fixtures" / "inexpressible-fire-forget.js"
ART = REPO / "command-center" / "receipts" / "IMP-0160.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def load_bearing_unexpressed(result) -> list:
    return [e for e in result.ledger if e.load_bearing and not e.expressed]


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0160" not in text:
        return fail("sentinel-absent")

    good = import_path(GOOD)
    if validate_workflow(good.workflow):
        return fail("good corpus does not validate")
    date_on_good = [e for e in good.ledger if e.kind == "date-now"]
    ff_on_good = [e for e in good.ledger if e.kind == "fire-forget"]
    if date_on_good or ff_on_good:
        return fail(
            "good state fired planted constructs "
            + json.dumps([e.to_json() for e in date_on_good + ff_on_good])
        )

    bad_date = import_path(BAD_DATE)
    date_rows = [
        e
        for e in load_bearing_unexpressed(bad_date)
        if e.kind == "date-now"
    ]
    if not date_rows:
        return fail("Date.now planted construct was dropped (ledger silent)")
    fanouts = [n for n in bad_date.workflow.nodes if isinstance(n, FanOut)]
    if not fanouts or len(fanouts[0].units) != 4:
        return fail("lossy import dropped fan-out while recording Date.now")

    bad_ff = import_path(BAD_FF)
    ff_rows = [
        e
        for e in load_bearing_unexpressed(bad_ff)
        if e.kind == "fire-forget"
    ]
    if not ff_rows:
        return fail("fire-and-forget agent() was dropped or normalised silently")
    unit_ids = {u.id for u in bad_ff.workflow.units}
    if "ghost" in unit_ids:
        return fail("fire-and-forget normalised into blocking WorkUnit 'ghost'")

    payload = {
        "probe": "probe2-lossy-ledger",
        "unit_id": UNIT,
        "pass": True,
        "good_silent": True,
        "date_now_ledgered": True,
        "fire_and_forget_ledgered": True,
        "fire_and_forget_not_normalised": True,
        "date_now_rows": [e.to_json() for e in date_rows],
        "fire_forget_rows": [e.to_json() for e in ff_rows],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "good_silent=True date_now_ledgered=True fire_forget_ledgered=True "
        "not_normalised=True"
    )
    print(f"SUCCESS:{UNIT}-probe2 lossy ledger both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
