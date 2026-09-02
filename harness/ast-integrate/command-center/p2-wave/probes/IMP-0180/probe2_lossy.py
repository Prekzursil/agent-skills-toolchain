#!/usr/bin/env python3
"""Probe 2: planted lossy fusion must fail the inverse (detector fires).

Mechanically different from probe 1: this probe mutates each encoding by
dropping recovery material, then requires inverse_holds == False, and
requires the same detector to stay silent on the honest encoding
(both-states). Names the missing source fingerprint on the broken state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fusion import (  # noqa: E402
    STRATEGIES,
    fuse,
    inverse_holds,
    make_lossy,
    source_a,
    source_b,
    structural_fingerprint,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0180-probe2 {msg}")
    return 1


def main() -> int:
    a = source_a()
    b = source_b()
    fp_a = structural_fingerprint(a)
    fp_b = structural_fingerprint(b)
    missing_named = 0
    silent_good = 0
    fired_bad = 0

    for strategy in STRATEGIES:
        honest = fuse(strategy, a, b)
        good = inverse_holds(strategy, a, b, honest)
        if not good["ok"]:
            return fail(f"{strategy} detector noisy on honest fusion: {good['error']}")
        silent_good += 1

        lossy = make_lossy(honest)
        bad = inverse_holds(strategy, a, b, lossy)
        if bad["ok"]:
            return fail(f"{strategy} detector silent on lossy fusion (got {bad['got']})")
        fired_bad += 1

        got = set(bad["got"])
        lost = {fp_a, fp_b} - got
        if not lost and bad["error"] is None:
            return fail(f"{strategy} lossy failed without naming a missing fingerprint")
        named = sorted(lost) if lost else list(bad["want"])
        print(
            "DETECT "
            f"{strategy} fired_on_lossy=True silent_on_honest=True "
            f"missing={','.join(x[:12] for x in named)} "
            f"err={bad['error']}"
        )
        missing_named += 1

    if silent_good != 8 or fired_bad != 8 or missing_named != 8:
        return fail(
            f"both-states incomplete silent_good={silent_good} "
            f"fired_bad={fired_bad} named={missing_named}"
        )

    payload = {
        "probe": "probe2-lossy",
        "unit_id": "IMP-0180",
        "pass": True,
        "silent_on_honest": silent_good,
        "fired_on_lossy": fired_bad,
        "named_missing_fingerprint": missing_named,
        "both_states": True,
        "fp_a": fp_a,
        "fp_b": fp_b,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:IMP-0180-probe2 planted lossy fusion fails inverse; honest stays green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
