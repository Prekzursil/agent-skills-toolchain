#!/usr/bin/env python3
"""Probe 1: generator control — all-conditions-satisfied fixture is ACCEPTED.

Proves the generator can produce a passing artifact and the reducer is not
simply rejecting everything. Also asserts exit-code-zero on that same
workspace is not what produced ACCEPT (the flag exit_code_consulted_for_complete
must stay false, and stripping the other eleven conditions must REJECT).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import generator as G  # noqa: E402
from reducer import judge  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0416.json"
SENTINEL = "SENTINEL:IMP-0416:REDUCER-NEGATIVE-CONTROLS"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0416-probe1 {msg}")
    return 1


def main() -> int:
    suite = G.materialize(HERE / "fixtures", REPO)
    pos = suite["positive"]
    print(
        f"positive_verdict={pos['reducer_verdict']} "
        f"failing={pos['failing']} "
        f"exit_consulted={pos['exit_code_consulted_for_complete']}"
    )
    if pos["reducer_verdict"] != "ACCEPT":
        return fail(f"positive control REJECTED failing={pos['failing']}")
    if pos["failing"]:
        return fail(f"ACCEPT with failing={pos['failing']}")
    if pos["exit_code_consulted_for_complete"] is not False:
        return fail("exit code was consulted for COMPLETE")

    ez = suite["exit_zero_alone"]
    print(
        f"exit_zero_alone_verdict={ez['reducer_verdict']} "
        f"failing={ez['failing']}"
    )
    if ez["reducer_verdict"] != "REJECT":
        return fail("exit-zero-alone was ACCEPTED")
    if ez["exit_code_consulted_for_complete"] is not False:
        return fail("exit-zero-alone consulted exit code")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    pc = doc.get("positive_control") or {}
    if pc.get("reducer_verdict") != "ACCEPT":
        return fail("receipt positive_control is not ACCEPT")

    # Live re-judge of the durable positive workspace, not a cached field.
    live = judge(HERE / "fixtures" / "positive", process_exit_code=0)
    if live["verdict"] != "ACCEPT":
        return fail(f"re-judge positive {live['verdict']} {live['failing']}")

    print("SUCCESS:IMP-0416-probe1 positive-control ACCEPT and exit-zero-alone REJECT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
