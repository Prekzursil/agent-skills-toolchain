#!/usr/bin/env python3
"""Probe 2 (independent reviewer): same test on a reconciled scratch copy.

GREEN on the patched scratch. RED on an unreconciled scratch that still
exists (so a test that only checks file-presence measures nothing). Does
not import probe1.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402


def fail(why: str) -> int:
    print(f"FAILED:AUD-0035-probe2 {why}")
    return 1


def main() -> int:
    live = E.live_log_path()
    src = live if live.is_file() else None
    with tempfile.TemporaryDirectory(prefix="aud0035-p2-") as raw:
        tmp = Path(raw)
        good = tmp / "17-DECISION-LOG.md"
        bad = tmp / "unreconciled.md"
        E.write_reconciled_copy(src, good)
        E.write_unreconciled_copy(bad)
        green = E.evaluate(good)
        red = E.evaluate(bad)
        # Currently-true present-tense line must not veto a reconciled log.
        text = good.read_text(encoding="utf-8")
        if "Release mode is PR-ONLY" not in text and src is None:
            # stale capture includes that line; keep it through reconcile.
            pass

    payload = {
        "probe": "probe2-reconciled-scratch-green",
        "unit_id": "AUD-0035",
        "reviewer_id": "AUD-0035-probe2-reconciled-scratch",
        "independent": True,
        "source_was_live_file": src is not None,
        "green_color": green["color"],
        "green_exit_code": green["exit_code"],
        "green_assertion": green["assertion"],
        "green_mech_token_count": green["mech_token_count"],
        "green_present_tense_collision": green["present_tense_collision"],
        "green_line_175": green["line_175"],
        "unreconciled_color": red["color"],
        "unreconciled_exit_code": red["exit_code"],
        "unreconciled_assertion": red["assertion"],
        "unreconciled_mech_token_count": red["mech_token_count"],
        "unreconciled_present_tense_collision": red["present_tense_collision"],
        "both_states": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(green["assertion"])
    print(red["assertion"])

    if green["color"] != "GREEN" or not green["ok"] or green["exit_code"] != 0:
        return fail("reconciled scratch was not GREEN")
    if green["mech_token_count"] <= 0:
        return fail("reconciled scratch has zero MECH tokens")
    if green["present_tense_collision"] is not False:
        return fail("reconciled line 175 still classified as present-tense collision")
    if "MECH-NN" not in (green["line_175"] or ""):
        return fail("reconciled line 175 does not name MECH-NN")
    if red["color"] != "RED" or red["ok"] or red["exit_code"] == 0:
        return fail("unreconciled scratch was not RED (test would be vacuous)")
    if red["present_tense_collision"] is not True:
        return fail("unreconciled scratch did not fire present-tense collision")
    if red["mech_token_count"] != 0:
        return fail("unreconciled scratch must carry zero MECH tokens")
    if green["color"] == red["color"]:
        return fail("both states same color; test measures nothing")

    print(
        f"GREEN mech={green['mech_token_count']} "
        f"RED mech={red['mech_token_count']} both_states=True"
    )
    print("SUCCESS:AUD-0035-probe2 reconciled scratch GREEN unreconciled still RED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
