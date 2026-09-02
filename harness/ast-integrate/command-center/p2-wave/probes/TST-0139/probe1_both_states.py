#!/usr/bin/env python3
"""Probe 1: both-states 429 vs 529 on the live scheduler.

429 storm MUST reduce measured wave-2 arrival rate.
529 storm must not, must not shrink concurrency, and retries while siblings continue.
A harness that applies the same policy to both fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import http_storm_scheduler as S  # noqa: E402


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:TST-0139-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, sort_keys=True, default=str)[:4000])
    return 1


def main() -> int:
    both = S.both_states()
    print(
        json.dumps(
            {
                "probe": "probe1-both-states-429-vs-529",
                "unit_id": "TST-0139",
                "pass": both["pass"],
                "diverged": both["diverged"],
                "identical_mutant_collapses": both["identical_mutant_collapses"],
                "storm_429": both["storm_429"],
                "storm_529": both["storm_529"],
                "concurrency_529": {
                    k: both["concurrency_529"][k]
                    for k in (
                        "min_ceiling",
                        "max_inflight",
                        "ceiling_held",
                        "retry_count",
                        "siblings_continued",
                        "logical_count",
                        "simultaneous_ceiling",
                    )
                },
                "concurrency_samples": both["concurrency_529"]["samples"],
            },
            sort_keys=True,
        )
    )
    s429 = both["storm_429"]
    s529 = both["storm_529"]
    c529 = both["concurrency_529"]
    if s429["wave1_rate"] <= 0 or s529["wave1_rate"] <= 0:
        return fail("wave1 rate is zero; meter is dark")
    if not s429["rate_reduced"]:
        return fail("429 storm did not reduce arrival rate", s429)
    if s529["rate_reduced"]:
        return fail("529 storm reduced arrival rate (must not)", s529)
    if s429["wave2_rate"] == s529["wave2_rate"]:
        return fail("429 and 529 wave-2 rates are identical")
    if not both["diverged"]:
        return fail("policies did not diverge")
    if s529["concurrency_reduced"]:
        return fail("529 reduced program concurrency", s529)
    if not c529["ceiling_held"]:
        return fail("529 concurrency ceiling moved", c529)
    if c529["max_inflight"] < 1:
        return fail("concurrency meter recorded no in-flight samples", c529)
    if c529["logical_count"] <= c529["simultaneous_ceiling"]:
        return fail("logical count was not independent of simultaneous ceiling", c529)
    if c529["retry_count"] < 1:
        return fail("529 did not retry the affected unit", c529)
    if not c529["siblings_continued"]:
        return fail("siblings did not continue during 529 retry", c529)
    if not both["identical_mutant_collapses"]:
        return fail("identical-throttle mutant was silent in both states")
    if not both["pass"]:
        return fail("both_states aggregate failed", both)
    print(
        f"rate_429 {s429['wave1_rate']:.4f}->{s429['wave2_rate']:.4f} "
        f"rate_529 {s529['wave1_rate']:.4f}->{s529['wave2_rate']:.4f} "
        f"ceil_held={c529['ceiling_held']} retries={c529['retry_count']} "
        f"siblings={c529['siblings_continued']}"
    )
    print("SUCCESS:TST-0139-probe1 429 throttles arrival rate; 529 does not shrink concurrency")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
