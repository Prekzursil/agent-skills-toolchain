#!/usr/bin/env python3
"""Probe 1: ten fixtures spanning T0-T4; explanation reconstructs each dial."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from completeness import complete  # noqa: E402
from reconstruct import matches, recorded_dials  # noqa: E402
from rules import DIALS, FIXTURES  # noqa: E402
from selector import select  # noqa: E402

REPO = HERE.parents[3]
NOTE = REPO / (
    "command-center/design/council/"
    "CNL-0013-auto-composed-council-the-selector-and-its-mandatory-expla.md"
)


def main() -> int:
    if len(FIXTURES) != 10:
        print(f"FAILED:CNL-0013-probe1 fixture-count={len(FIXTURES)}")
        return 1
    tiers = sorted({f["risk_tier"] for f in FIXTURES})
    if tiers != ["T0", "T1", "T2", "T3", "T4"]:
        print(f"FAILED:CNL-0013-probe1 tiers={tiers}")
        return 1

    live_rows = []
    for fx in FIXTURES:
        rec = select(fx["task_description"], fx["risk_tier"])
        if not complete(rec):
            print(f"FAILED:CNL-0013-probe1 incomplete {fx['id']}")
            return 1
        ok, why = matches(rec)
        if not ok:
            print(f"FAILED:CNL-0013-probe1 reconstruct {fx['id']} {why}")
            return 1
        live_rows.append((fx, rec))
        print(
            f"fixture {fx['id']} tier={fx['risk_tier']} class={rec['task_class']} "
            f"protocol={rec['protocol']} reconstruct=ok"
        )

    if not NOTE.is_file():
        print("FAILED:CNL-0013-probe1 design-note-absent")
        return 1
    note = json.loads(NOTE.read_text(encoding="utf-8"))
    recorded = note.get("fixtures") or []
    if len(recorded) != 10:
        print(f"FAILED:CNL-0013-probe1 note-fixture-count={len(recorded)}")
        return 1
    note_tiers = sorted({str(r.get("risk_tier")) for r in recorded})
    if note_tiers != ["T0", "T1", "T2", "T3", "T4"]:
        print(f"FAILED:CNL-0013-probe1 note-tiers={note_tiers}")
        return 1
    by_id = {r.get("id"): r for r in recorded}
    for fx, rec in live_rows:
        row = by_id.get(fx["id"])
        if not isinstance(row, dict):
            print(f"FAILED:CNL-0013-probe1 note-missing {fx['id']}")
            return 1
        expl = row.get("explanation") or {}
        ok, why = matches(expl)
        if not ok:
            print(f"FAILED:CNL-0013-probe1 note-reconstruct {fx['id']} {why}")
            return 1
        live = recorded_dials(rec)
        noted = recorded_dials(expl)
        if live != noted:
            print(f"FAILED:CNL-0013-probe1 note-drift {fx['id']} live={live} noted={noted}")
            return 1
        if set(live) != set(DIALS):
            print(f"FAILED:CNL-0013-probe1 dial-set {fx['id']} {sorted(live)}")
            return 1
        print(f"note {fx['id']} reconstruct=ok live-match=ok")

    print("SUCCESS:CNL-0013-probe1 ten fixtures reconstruct without selector.select")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
