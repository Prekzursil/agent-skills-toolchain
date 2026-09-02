#!/usr/bin/env python3
"""Probe 1: looping collapse stop vs productive non-stop, six protocols."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from simulator import HORIZON, measure  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0263-probe1 {msg}")
    return 1


def main() -> int:
    live = measure()
    if not live["looping_ok"]:
        return fail("looping cast did not collapse and stop within 2 rounds")
    if not live["productive_ok"]:
        return fail("productive cast stop fired or used a round cap")
    bundle = live["bundle"]
    looping = [r for r in bundle["runs"] if r["cast"] == "looping"]
    productive = [r for r in bundle["runs"] if r["cast"] == "productive"]
    if len(looping) != 6 or len(productive) != 6:
        return fail(f"expected 6+6 protocol runs, got {len(looping)}/{len(productive)}")
    curves = {}
    for run in looping:
        pid = run["protocol_id"]
        stop = run["stop"]
        curve = [row["gain"] for row in run["curve"]]
        curves[pid] = {
            "cast": "looping",
            "per_round_gain": curve,
            "collapse_round": stop.get("collapse_round"),
            "stop_round": stop.get("stop_round"),
            "delta": stop.get("delta_from_collapse"),
            "floor_cross": run["gain_crosses_floor"],
        }
        if stop.get("reason") != "information_gain":
            return fail(f"{pid} looping reason={stop.get('reason')}")
        if int(stop["delta_from_collapse"]) > 2:
            return fail(f"{pid} stop too late: {stop}")
        if int(stop["stop_round"]) > HORIZON:
            return fail(f"{pid} stop beyond measured horizon")
        if stop.get("hardcoded_round_cap"):
            return fail(f"{pid} looping used a hardcoded cap")
    for run in productive:
        pid = run["protocol_id"]
        stop = run["stop"]
        if stop.get("fired"):
            return fail(f"{pid} productive stop fired: {stop}")
        if stop.get("reason") != "still_gaining":
            return fail(f"{pid} productive reason={stop.get('reason')}")
        if any(row["gain"] <= 0.0 for row in run["curve"]):
            return fail(f"{pid} productive gain hit floor; metric is a counter")
        last = int(run["curve"][-1]["round"])
        loop_stop = next(
            r["stop"]["stop_round"] for r in looping if r["protocol_id"] == pid
        )
        if last <= int(loop_stop):
            return fail(
                f"{pid} productive horizon {last} did not outrun looping stop {loop_stop}"
            )
    print(
        json.dumps(
            {
                "probe": "probe1-loop-and-productive",
                "protocols": [r["protocol_id"] for r in looping],
                "looping": curves,
                "productive_per_round_gain": {
                    r["protocol_id"]: [row["gain"] for row in r["curve"]]
                    for r in productive
                },
                "simulate_py_present": live["simulate_py_present"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("looping_stop_within_2=True productive_did_not_stop=True protocols=6")
    print("SUCCESS:TST-0263-probe1 looping collapse stop and productive control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
