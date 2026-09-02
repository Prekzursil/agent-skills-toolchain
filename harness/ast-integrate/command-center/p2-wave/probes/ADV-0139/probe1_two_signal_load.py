#!/usr/bin/env python3
"""Probe 1: two-signal load detector vs naive config-only walker."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import load_probe as LP  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0139-probe1 {msg}")
    return 1


def main() -> int:
    ctrl = LP.run_fixture_control()
    live = ctrl["known_loaded"]["verdict"]
    disabled = ctrl["known_disabled"]["verdict"]
    if live != "LOADED":
        return fail(f"known-loaded verdict={live} {ctrl['live']}")
    if disabled != "NOT-LOADED":
        return fail(f"known-disabled verdict={disabled} {ctrl['disabled']}")
    if ctrl["wrong_scope"]["verdict"] != "NOT-LOADED":
        return fail(f"wrong-scope not separated {ctrl['wrong_scope']}")
    if not ctrl["naive_collapsed"]:
        return fail(
            "naive walker did not collapse loaded vs disabled/shadow "
            f"{ctrl['naive']}"
        )
    if not ctrl["two_signal_separated"]:
        return fail("two-signal did not separate the two known states")
    naive = ctrl["naive"]
    if naive["adv0139-live"] != naive["adv0139-disabled"]:
        return fail("naive unexpectedly separated live vs disabled")
    out = HERE / "probe1-load-control.raw.json"
    out.write_text(json.dumps(ctrl, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "known_loaded=LOADED known_disabled=NOT-LOADED "
        "wrong_scope=NOT-LOADED naive_collapsed=True "
        f"naive_names={naive['names']}"
    )
    print("SUCCESS:ADV-0139-probe1 two-signal load detector separates both states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
