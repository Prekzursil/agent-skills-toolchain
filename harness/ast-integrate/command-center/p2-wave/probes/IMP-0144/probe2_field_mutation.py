#!/usr/bin/env python3
"""Probe 2: drop one load-bearing event field; byte-equality must go red.

Control: drop debug_note (non-load-bearing); plan stays byte-identical.
Both-states: intact log still replays equal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / S.RECEIPT_REL


def main() -> int:
    run = S.field_mutation()
    printable = {k: run[k] for k in sorted(run) if k != "pass"}
    print(json.dumps(printable, sort_keys=True))
    if not run["pass"]:
        print("FAILED:IMP-0144-probe2 mutation control did not pass")
        return 1
    if run["item_plan_equal"] is not False:
        print("FAILED:IMP-0144-probe2 dropping a fan-out item did not change the plan")
        return 1
    if run["params_equal"] is not False:
        print("FAILED:IMP-0144-probe2 dropping params did not go red")
        return 1
    if run["note_equal"] is not True:
        print("FAILED:IMP-0144-probe2 dropping debug_note changed the plan (vacuous detector)")
        return 1
    if run["intact_equal"] is not True:
        print("FAILED:IMP-0144-probe2 intact log no longer replays")
        return 1
    if not ART.is_file():
        print("FAILED:IMP-0144-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0144-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0144" not in text:
        print("FAILED:IMP-0144-probe2 sentinel absent")
        return 1
    print(
        f"params_red={run['params_equal'] is False} "
        f"item_red={run['item_plan_equal'] is False} "
        f"note_control={run['note_equal']} intact={run['intact_equal']}"
    )
    print("SUCCESS:IMP-0144-probe2 load-bearing field drop turns byte-equality red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
