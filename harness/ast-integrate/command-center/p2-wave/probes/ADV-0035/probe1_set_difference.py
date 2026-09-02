#!/usr/bin/env python3
"""Probe 1: declared-versus-observed set difference with coverage guard.

Mechanically different from probe 2 (no grant mutation, no test re-run).
Historical traces only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import reconcile as R  # noqa: E402

from plugin.permission_diff import canonicalize  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:ADV-0035-probe1 {msg}")
    return 1


def main() -> int:
    pack = R.load_fixture_pack()
    analysis = R.analyze_fixtures(pack)
    diffs = {d["id"]: d for d in analysis["diffs"]}
    bash = canonicalize("Bash")
    write = canonicalize("Write")

    honest = diffs["fx-honest"]
    over = diffs["fx-overdeclare-unused"]
    under = diffs["fx-underdeclare"]
    thin = diffs["fx-thin-trace"]
    unex = diffs["fx-unexercised-needed"]

    payload = {
        "instrument": "set-difference",
        "coverage_threshold": analysis["coverage_threshold"],
        "diffs": analysis["diffs"],
        "live_census": R.live_catalog_census(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    if honest["over_declared_raw"] or honest["under_declared"]:
        return _fail("honest fixture is not empty on over/under")
    if not honest["coverage_ok"]:
        return _fail("honest coverage unexpectedly thin")
    if bash not in over["over_declared_candidates"]:
        return _fail("planted unused Bash not in over-declared candidates")
    if over["under_declared"]:
        return _fail("overdeclare fixture has under-declared noise")
    if write not in under["under_declared"]:
        return _fail("planted undeclared Write not in under-declared list")
    if bash not in thin["over_declared_raw"]:
        return _fail("thin-trace set-difference missed Bash (guard would be vacuous)")
    if thin["coverage_ok"] or bash in thin["over_declared_candidates"]:
        return _fail("coverage guard failed to suppress thin-trace over-declaration")
    if thin["coverage"]["fraction"] >= analysis["coverage_threshold"]:
        return _fail("thin-trace fixture is not below the stated fraction")
    if write not in unex["over_declared_raw"]:
        return _fail("unexercised Write not visible to set-difference")
    if not unex["coverage_ok"]:
        return _fail("unexercised-needed coverage should pass the floor so probe 2 can refute")
    if write in unex["observed_from_traces"]:
        return _fail("unexercised Write should be absent from traces")

    census = payload["live_census"]
    if census["work_unit_n"] < 1:
        return _fail("catalog work_units missing")
    if census["coverage_ok_n"] != 0:
        return _fail("live coverage_ok_n must stay 0 without recorded traces")

    print("SUCCESS:ADV-0035-probe1 set-difference and coverage guard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
