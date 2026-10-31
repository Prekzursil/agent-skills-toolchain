#!/usr/bin/env python3
"""Probe 1: scheduled-task and service state as reported by the OS."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

RAW = HERE / "probe1-os-state.raw.txt"
JSON_OUT = HERE / "probe1-os-state.json"
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def main() -> int:
    os_state = E.probe_os()
    text = E.text_p1(os_state)
    RAW.write_text(text + "\n", encoding="utf-8")
    E.dump(JSON_OUT, {"probe": "probe1-os-state", "os": os_state})
    print(text)

    try:
        art_text, doc = E.load_artifact()
    except FileNotFoundError:
        print("FAILED:AUD-0066-probe1 artifact missing")
        return 1
    if E.SENTINEL not in art_text:
        print("FAILED:AUD-0066-probe1 catalog sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in BLOCKED:
        print(f"FAILED:AUD-0066-probe1 self-declared {st}")
        return 1
    live = (doc.get("os_state") or {})
    if bool(live.get("windows_tools", {}).get("available")) != bool(
        os_state["windows_tools"]["available"]
    ):
        print("FAILED:AUD-0066-probe1 windows-tools availability drifted")
        return 1
    if int(live.get("n_linux_matching_units", -1)) != int(
        os_state["n_linux_matching_units"]
    ):
        print(
            "FAILED:AUD-0066-probe1 linux matching-unit drift "
            f"artifact={live.get('n_linux_matching_units')} "
            f"live={os_state['n_linux_matching_units']}"
        )
        return 1
    if int(live.get("n_declared", -1)) != int(os_state["n_declared"]):
        print("FAILED:AUD-0066-probe1 declared-row count drifted")
        return 1
    print("SUCCESS:AUD-0066-probe1 OS scheduled-task/service state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
