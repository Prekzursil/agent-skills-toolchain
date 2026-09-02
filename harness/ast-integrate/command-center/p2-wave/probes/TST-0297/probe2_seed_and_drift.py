#!/usr/bin/env python3
"""Probe 2: environment-drift alarm and variance-floor refusal."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "bench"))

import cases as C  # noqa: E402
import env_capture as E  # noqa: E402
import variance as V  # noqa: E402

RECEIPT = REPO / "command-center/receipts/TST-0297.json"
SEED = 20260824


def fail(msg: str) -> int:
    print(f"FAILED:TST-0297-probe2 {msg}")
    return 1


def main() -> int:
    fixture = C.load_cases()
    baseline = E.capture_environment(
        seed=SEED,
        model_id="fixture-model",
        model_snapshot="snap-0",
        temperature=0.0,
        concurrency=1,
        arrival_rate=1.0,
    )
    same = E.capture_environment(
        seed=SEED,
        model_id="fixture-model",
        model_snapshot="snap-0",
        temperature=0.0,
        concurrency=1,
        arrival_rate=1.0,
        tool_versions_map=baseline["tool_versions"],
    )
    match = E.drift_report(baseline, same)
    if match["drifted"]:
        return fail("identical captures flagged as drift")

    drifted_env = E.mutate_env(baseline, model_snapshot="snap-1-other")
    drift = E.drift_report(baseline, drifted_env)
    if not drift["drifted"]:
        return fail("snapshot change was not flagged")
    fields = {d["field"] for d in drift["differing_fields"]}
    if "model_snapshot" not in fields:
        return fail(f"drift fields {fields} omit model_snapshot")

    dist = V.null_delta_distribution(fixture, baseline, n=10)
    floor = float(dist["variance_floor"])
    live_zero = V.report_improvement(
        baseline_env=baseline,
        candidate_env=same,
        delta=0.0,
        floor=floor,
    )
    if live_zero["reported"] or live_zero["status"] != "NOT-A-RESULT":
        return fail("zero delta on a zero floor was reported as a result")

    small = V.report_improvement(
        baseline_env=baseline, candidate_env=same, delta=0.01, floor=0.05
    )
    if small["reported"] or small["status"] != "NOT-A-RESULT":
        return fail("delta inside the floor was reported")
    large = V.report_improvement(
        baseline_env=baseline, candidate_env=same, delta=0.06, floor=0.05
    )
    if not large["reported"] or large["status"] != "RESULT":
        return fail("delta above the floor was refused")
    at_floor = V.report_improvement(
        baseline_env=baseline, candidate_env=same, delta=0.05, floor=0.05
    )
    if at_floor["reported"]:
        return fail("delta equal to the floor was reported")

    drifted_cmp = V.report_improvement(
        baseline_env=baseline, candidate_env=drifted_env, delta=0.5, floor=floor
    )
    if drifted_cmp["reported"] or drifted_cmp["status"] != "DRIFT":
        return fail("drifted comparison was not refused")
    if drifted_cmp.get("delta") is not None:
        return fail("drifted comparison leaked a delta")

    if RECEIPT.is_file():
        doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"receipt self-declared {doc.get('state')}")
        alarm = doc.get("environment_drift_alarm") or {}
        if alarm.get("snapshot_change_flagged") is not True:
            return fail("receipt missing snapshot_change_flagged")
        if alarm.get("silently_compared") is True:
            return fail("receipt claims a drifted run was compared")
        gate = doc.get("floor_gate") or {}
        if gate.get("below_floor_refused") is not True:
            return fail("receipt missing below_floor_refused")
        if gate.get("above_floor_reported") is not True:
            return fail("receipt missing above_floor_reported")

    payload = {
        "match_drifted": match["drifted"],
        "snapshot_change_flagged": drift["drifted"],
        "differing_fields": sorted(fields),
        "zero_delta_status": live_zero["status"],
        "below_floor_refused": small["status"] == "NOT-A-RESULT",
        "above_floor_reported": large["status"] == "RESULT",
        "at_floor_refused": at_floor["status"] == "NOT-A-RESULT",
        "drift_refused": drifted_cmp["status"] == "DRIFT",
        "live_floor": floor,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"drift_flagged={drift['drifted']} below_floor_refused=True "
        f"above_floor_reported=True live_floor={floor}"
    )
    print("SUCCESS:TST-0297-probe2 drift alarm and variance-floor gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
