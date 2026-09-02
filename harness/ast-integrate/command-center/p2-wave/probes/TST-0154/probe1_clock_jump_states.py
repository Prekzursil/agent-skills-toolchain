#!/usr/bin/env python3
"""Probe 1: unit state across injected backward and forward clock jumps."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lab import measure_clock_jumps  # noqa: E402

ART = REPO / "command-center/receipts/TST-0154.json"
SENTINEL = "SUCCESS:TST-0154"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0154-probe1 {msg}")
    return 1


def main() -> int:
    live = measure_clock_jumps()
    print(json.dumps(live, indent=2, sort_keys=True, default=str))
    if not live.get("pass"):
        return fail("clock-jump campaign did not pass")
    if not live.get("production_survives_jumps"):
        return fail("production did not survive wall jumps")
    if not live.get("wall_mutant_fails_both_directions"):
        return fail("wall-clock mutant did not fail both directions")
    if not live.get("both_states_timeout_still_fires"):
        return fail("real timeout did not fire during jump campaign")
    if not live.get("both_states_early_not_timeout"):
        return fail("timeout fired before monotonic elapsed reached the bound")
    if live.get("running_survives_backward") is not True:
        return fail("running unit timed out on backward jump")
    if live.get("running_survives_forward") is not True:
        return fail("running unit timed out on forward jump")
    if live.get("stalled_survives_backward") is not True:
        return fail("stalled unit marked fresh on backward jump")
    if live.get("stalled_survives_forward") is not True:
        return fail("stalled unit lost stall on forward jump")

    if ART.is_file() and ART.stat().st_size > 0:
        text = ART.read_text(encoding="utf-8")
        if SENTINEL not in text:
            return fail("receipt-sentinel-absent")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"receipt-self-declared {st}")

    print(
        "running survived backward+forward; stalled stayed stalled; "
        f"timeout_mid={live.get('timeout_mid_state')} "
        f"timeout_fired={live.get('timeout_fired_state')}; "
        "wall mutant failed both directions"
    )
    print("SUCCESS:TST-0154-probe1 clock-jump both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
