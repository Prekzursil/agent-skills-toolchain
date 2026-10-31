#!/usr/bin/env python3
"""Probe 1: chaos injection + 1..N fault sweep + partial-contribution census.

Live named probe for IMP-0330. Starts from the public resilience API.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from council.resilience import (  # noqa: E402
    FaultKind,
    chaos_three_faults,
    fault_injection_sweep,
    refuse_at_failed_count,
)


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0330-probe1 {msg}")
    return 1


def main() -> int:
    chaos = chaos_three_faults(n_seats=5, required_quorum=4, timeout_s=0.05)
    if chaos["aborted"]:
        return _fail("council aborted on mixed faults")
    if not chaos["three_kinds_isolated"]:
        return _fail(f"fault kinds {chaos['fault_kinds_observed']}")
    if not chaos["census"]["all_isolated_partials_retained"]:
        return _fail(f"census missing {chaos['census']['missing_partials']}")
    if may_conclude_from_artifact(chaos["artifact"]) is None:
        return _fail("artifact missing quorum decision")

    sweeps = []
    for kind in (FaultKind.CRASH, FaultKind.TIMEOUT, FaultKind.MALFORMED):
        sweep = fault_injection_sweep(
            n_seats=5, required_quorum=4, kind=kind, timeout_s=0.05
        )
        if sweep["threshold_merely_documented"] or not sweep["threshold_enforced"]:
            return _fail(f"{kind.value} threshold not enforced: {sweep}")
        expected = refuse_at_failed_count(5, 4)
        if sweep["observed_refuse_at_failed_count"] != expected:
            return _fail(
                f"{kind.value} refuse-at {sweep['observed_refuse_at_failed_count']} != {expected}"
            )
        if any(r["aborted"] for r in sweep["rows"]):
            return _fail(f"{kind.value} aborted the council")
        if any(not r["census_ok"] for r in sweep["rows"] if r["failed"] > 0):
            return _fail(f"{kind.value} census lost a partial")
        if any(not r["matches_enforced_identity"] for r in sweep["rows"]):
            return _fail(f"{kind.value} decision diverged from healthy>=Q identity")
        sweeps.append(sweep)

    extra = fault_injection_sweep(
        n_seats=7, required_quorum=5, kind=FaultKind.CRASH, timeout_s=0.05
    )
    if not extra["threshold_enforced"]:
        return _fail("N=7 Q=5 threshold not enforced")
    if extra["observed_refuse_at_failed_count"] != 3:
        return _fail(f"N=7 refuse-at {extra['observed_refuse_at_failed_count']} != 3")

    summary = {
        "chaos": {
            "aborted": chaos["aborted"],
            "census_ok": chaos["census"]["all_isolated_partials_retained"],
            "fault_kinds_observed": chaos["fault_kinds_observed"],
            "three_kinds_isolated": chaos["three_kinds_isolated"],
            "isolated_count": chaos["census"]["isolated_count"],
        },
        "pass": True,
        "probe": "probe1-chaos-sweep",
        "refuse_boundary": {
            "n5_q4_failed_count": 2,
            "n5_q4_fraction": 0.4,
            "n7_q5_failed_count": 3,
            "n7_q5_fraction": 3 / 7,
            "rule": "refuse iff healthy < required_quorum (required frozen on original N)",
            "threshold_enforced": True,
        },
        "sweeps": [
            {
                "kind": s["kind"],
                "n_seats": s["n_seats"],
                "observed_refuse_at_failed_count": s["observed_refuse_at_failed_count"],
                "required_quorum": s["required_quorum"],
                "rows": [
                    {
                        "decision": r["decision"],
                        "failed": r["failed"],
                        "healthy": r["healthy"],
                    }
                    for r in s["rows"]
                ],
                "threshold_enforced": s["threshold_enforced"],
            }
            for s in sweeps + [extra]
        ],
        "unit_id": "IMP-0330",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "refuse_boundary n=5 q=4 at_failed=2 fraction=0.4 enforced=True "
        "n=7 q=5 at_failed=3"
    )
    print("SUCCESS:IMP-0330-probe1 chaos isolation, sweep boundary, partial census")
    return 0


def may_conclude_from_artifact(artifact: dict) -> str | None:
    q = artifact.get("quorum") or {}
    return q.get("decision")


if __name__ == "__main__":
    raise SystemExit(main())
