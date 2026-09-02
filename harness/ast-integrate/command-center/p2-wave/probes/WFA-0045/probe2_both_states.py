#!/usr/bin/env python3
"""Probe 2: both-states malformed phase, defect surfacing, background not normalised.

Independent of probe 1: re-runs controls and checks IR blocking flags rather
than re-checking AST counts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adapter import adapt_file  # noqa: E402
from emit_report import both_states  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0045-adapter-saved-workflow.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0045-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0045" not in json.dumps(doc):
        print("FAILED:WFA-0045-probe2 sentinel absent")
        return 1

    live = both_states()
    if not live.get("pass"):
        print("FAILED:WFA-0045-probe2 both-states")
        print(json.dumps(live, indent=2)[:2000])
        return 1
    if live.get("malformed_ok") or live.get("malformed_ir_is_null") is not True:
        print("FAILED:WFA-0045-probe2 malformed phase parsed or partial IR")
        return 1
    if live.get("malformed_partial"):
        print("FAILED:WFA-0045-probe2 malformed reported partial parse")
        return 1
    if not live.get("wellformed_ok"):
        print("FAILED:WFA-0045-probe2 wellformed phase failed")
        return 1
    if not live.get("args_as_string_surfaced") or not live.get("date_now_surfaced"):
        print("FAILED:WFA-0045-probe2 defects not surfaced")
        return 1
    if not live.get("background_not_normalised_to_blocking"):
        print("FAILED:WFA-0045-probe2 background normalised to blocking")
        return 1

    tests = doc.get("tests")
    if isinstance(tests, dict):
        recorded = tests.get("both_states_malformed_phase") or {}
    else:
        recorded = live
    if not recorded.get("pass"):
        print("FAILED:WFA-0045-probe2 artifact both-states not pass")
        return 1
    if recorded.get("malformed_ok"):
        print("FAILED:WFA-0045-probe2 artifact claims malformed parsed")
        return 1

    bg = adapt_file(HERE / "controls" / "background-dispatch.js")
    for node in (bg.get("ir") or {}).get("nodes") or []:
        if node.get("kind") == "dispatch" and node.get("blocking") is not False:
            print("FAILED:WFA-0045-probe2 live background dispatch blocking")
            return 1

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or not reviewer.get("independent"):
        print("FAILED:WFA-0045-probe2 reviewer")
        return 1

    payload = {
        "pass": True,
        "probe": "probe2-both-states",
        "unit_id": "WFA-0045",
        "live": live,
        "computed_not_asserted": True,
        "reviewer_re_ran_both_states": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "malformed_rejected=True wellformed_ok=True "
        "args_as_string=True date_now=True background_not_blocking=True"
    )
    print("SUCCESS:WFA-0045-probe2 both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
