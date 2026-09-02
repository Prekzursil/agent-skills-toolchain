#!/usr/bin/env python3
"""Probe 1: both-states per named guard, against reproductions.

Must fire on the broken fixture and stay silent on the healthy fixture
for background, win-arg-limit, progress-only, and schema+MCP. Then check
FAILURE-MODES.json recorded the same controls and is not self-declared
BLOCKED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import both_states as B  # noqa: E402

ART = REPO / "command-center/phase3/A6/FAILURE-MODES.json"


def main() -> int:
    ctrl = B.both_states()
    for name, ok in (ctrl.get("checks") or {}).items():
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:ARC-0040-probe1 {name}")
            return 1
    if not ctrl.get("pass"):
        print(f"FAILED:ARC-0040-probe1 failed={ctrl.get('failed')}")
        return 1

    arg = ctrl["guards"]["win_arg_limit"]
    print(
        "estate_payload_len="
        f"{arg['estate_payload_len']} assembled_inline_utf16="
        f"{arg['assembled_inline_utf16']} assembled_prompt_file_utf16="
        f"{arg['assembled_prompt_file_utf16']} "
        f"linux_206={arg['linux_createprocess_206_reproduced']}"
    )
    if not ART.is_file():
        print("FAILED:ARC-0040-probe1 FAILURE-MODES.json missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0040-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:ARC-0040" not in text:
        print("FAILED:ARC-0040-probe1 sentinel absent")
        return 1
    recorded = (doc.get("guard_controls") or {}).get("checks") or {}
    for name, ok in ctrl["checks"].items():
        if recorded.get(name) is not True:
            print(f"FAILED:ARC-0040-probe1 artifact missing check {name}")
            return 1
        if bool(recorded.get(name)) != bool(ok):
            print(f"FAILED:ARC-0040-probe1 artifact drift {name}")
            return 1
    live_inline = int(arg["assembled_inline_utf16"])
    art_inline = int(doc.get("assembled_inline_utf16") or 0)
    if live_inline != art_inline:
        print("FAILED:ARC-0040-probe1 assembled_inline_utf16 drift")
        return 1
    print("SUCCESS:ARC-0040-probe1 both-states per guard against reproductions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
