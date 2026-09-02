#!/usr/bin/env python3
"""Probe 2 / reviewer control: known-broken $schema fixture must fire.

A reviewer who only re-reads the healthy report has verified nothing. This
probe re-starts both clients against hooks.json with a `$schema` key and
requires Codex to load ZERO hooks while Cursor still loads hooks. The
rejected key is identified by name.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import observe_schema_control  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0100-p2-") as tmp:
        ctrl = observe_schema_control(Path(tmp))

    if ctrl.get("key") != "$schema":
        print(f"FAILED:CNF-0100-probe2 silent-rejected key not named: {ctrl.get('key')!r}")
        return 1
    if not ctrl.get("fires"):
        print("FAILED:CNF-0100-probe2 detector did not fire on $schema fixture")
        print(json.dumps(ctrl, indent=2)[:2000])
        return 1
    if ctrl.get("codex_hooks_n") != 0:
        print(
            "FAILED:CNF-0100-probe2 Codex still loaded hooks; "
            "enumerating the config file would also look loaded"
        )
        return 1
    if ctrl.get("cursor_hooks_n", 0) < 1:
        print("FAILED:CNF-0100-probe2 Cursor also loaded zero hooks; control is silent")
        return 1
    if not all((ctrl.get("running") or {}).values()):
        print("FAILED:CNF-0100-probe2 a client was not running at observation")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2_detector_control",
                "fixture": ctrl["fixture"],
                "key_identified_by_name": ctrl["key"],
                "rejecting_client": ctrl["rejecting_client"],
                "effect": ctrl["effect"],
                "codex_hooks_n": ctrl["codex_hooks_n"],
                "cursor_hooks_n": ctrl["cursor_hooks_n"],
                "fires": True,
                "inventories_read_from_running_processes": True,
            },
            indent=2,
        )
    )
    print("SUCCESS:CNF-0100-probe2 detector control fires on $schema fixture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
