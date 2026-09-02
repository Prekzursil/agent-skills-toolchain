#!/usr/bin/env python3
"""Probe 1: both-states command-line length guard.

Under the measured threshold, dispatch stays inline. Over it, file transport
is chosen BEFORE spawn. Forced inline of the failing length reproduces the OS
error. Max one file retry; no third inline attempt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))

from arg_marshall import (  # noqa: E402
    FOLKLORE_CREATEPROCESS_CHARS,
    both_states,
    measure_failure_curve,
)

ART = REPO / "command-center" / "receipts" / "IMP-0424.json"
SENTINEL = "SENTINEL:IMP-0424:ARG-LIMIT-MEASURED"


def main() -> int:
    curve = measure_failure_curve(filler="A")
    states = both_states(curve)
    summary = {
        "last_ok_payload_len": curve.last_ok_payload_len,
        "first_fail_payload_len": curve.first_fail_payload_len,
        "threshold": curve.threshold,
        "fail_errno": curve.fail_errno,
        "fail_error_text": curve.fail_error_text,
        "folklore_32767_ok": curve.folklore_32767_ok,
        "folklore_used_as_threshold": curve.folklore_used_as_threshold,
        "createprocess_available": curve.createprocess_available,
        "spawn_api": curve.spawn_api,
        "attempts": len(curve.attempts),
        "states": {k: states[k] for k in states if k != "ok"},
        "ok": states["ok"],
    }
    print(json.dumps(summary, sort_keys=True, default=str))
    if curve.threshold >= curve.first_fail_payload_len:
        print("FAILED:IMP-0424-probe1 threshold not below measured fail")
        return 1
    if curve.threshold == FOLKLORE_CREATEPROCESS_CHARS:
        print("FAILED:IMP-0424-probe1 threshold is the remembered 32767 constant")
        return 1
    if not curve.fail_error_text:
        print("FAILED:IMP-0424-probe1 missing fail error text")
        return 1
    if not states["ok"]:
        print("FAILED:IMP-0424-probe1 both-states")
        return 1
    if states["under"]["transport"] != "inline":
        print("FAILED:IMP-0424-probe1 under-threshold must stay inline")
        return 1
    if states["over"]["transport"] != "file":
        print("FAILED:IMP-0424-probe1 over-threshold must use file transport")
        return 1
    if not states["forced_inline_over_fails"]["failed"]:
        print("FAILED:IMP-0424-probe1 forced inline of failing length did not fail")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0424-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:IMP-0424-probe1 sentinel-absent")
        return 1
    print(
        f"under={states['under']['transport']} over={states['over']['transport']} "
        f"first_fail={curve.first_fail_payload_len} threshold={curve.threshold} "
        f"inline_fail={states['forced_inline_over_fails']['failed']}"
    )
    print("SUCCESS:IMP-0424-probe1 both-states file-vs-inline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
