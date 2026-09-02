#!/usr/bin/env python3
"""Probe 1: run the new test on the current tree and require RED.

Also runs the captured stale fixture so a missing live file cannot hide a
detector that only fails on absence. The assertion message is printed
verbatim. This probe exits 0 when the test is red in both of those states.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402


def fail(why: str) -> int:
    print(f"FAILED:AUD-0035-probe1 {why}")
    return 1


def main() -> int:
    live = E.live_log_path()
    live_present = E.live_log_present()
    live_result = E.evaluate(live)
    subject, kind = E.current_tree_subject()
    current = E.evaluate(subject)
    fixture = E.write_stale_fixture()
    stale = E.evaluate(fixture)

    payload = {
        "probe": "probe1-current-tree-red",
        "unit_id": "AUD-0035",
        "live_path": str(live.relative_to(REPO)) if live.is_relative_to(REPO) else str(live),
        "live_present": live_present,
        "subject_kind": kind,
        "subject_path": str(subject.relative_to(REPO)) if subject.is_relative_to(REPO) else str(subject),
        "live_color": live_result["color"],
        "current_color": current["color"],
        "stale_color": stale["color"],
        "current_assertion": current["assertion"],
        "stale_assertion": stale["assertion"],
        "stale_mech_token_count": stale["mech_token_count"],
        "stale_present_tense_collision": stale["present_tense_collision"],
        "stale_line_175": stale["line_175"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(current["assertion"])

    if live_present and live_result["ok"]:
        return fail("current live decision log is already GREEN; test measures nothing")
    if live_result["color"] != "RED" or live_result["exit_code"] == 0:
        return fail("live-path evaluation was not RED")
    if current["color"] != "RED" or current["ok"] or current["exit_code"] == 0:
        return fail("current-tree subject was not RED")
    if not (current["assertion"] or "").startswith("FAIL:"):
        return fail("current-tree assertion message missing")
    if stale["color"] != "RED" or stale["ok"]:
        return fail("stale fixture was not RED")
    if stale["mech_token_count"] != 0:
        return fail("stale fixture must carry zero MECH tokens")
    if stale["present_tense_collision"] is not True:
        return fail("stale fixture line 175 did not fire present-tense collision")
    if "present tense" not in stale["assertion"].lower():
        return fail("stale assertion did not name present tense")
    if "0 MECH" not in stale["assertion"] and "zero MECH" not in stale["assertion"]:
        return fail("stale assertion did not name zero MECH tokens")
    if "Release mode is PR-ONLY" in (stale["line_175"] or ""):
        return fail("detector keyed off the currently-true line, not line 175")

    print(
        "RED live="
        f"{live_result['color']} current={current['color']} stale={stale['color']}"
    )
    print("SUCCESS:AUD-0035-probe1 current-tree RED with assertion message")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
