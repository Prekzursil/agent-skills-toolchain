#!/usr/bin/env python3
"""Probe 1: three+ observational properties, both-states, real artifact.

Known-good fixtures pass; known-broken fixtures fail. A checker silent in both
states is a delivery failure. Does not assert the model's opinion.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from properties import PLANTED_CREDENTIAL, run_property_battery  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0091-probe1 {msg}")
    return 1


def main() -> int:
    battery = run_property_battery()
    print(json.dumps(battery, sort_keys=True, separators=(",", ":")))
    if battery.get("planted_credential_kept_out_of_record") is not True:
        return fail("planted credential must stay out of the research record")
    if PLANTED_CREDENTIAL in json.dumps(battery):
        return fail("battery JSON contains the planted credential token")
    implemented = battery.get("implemented_properties") or []
    if len(implemented) < 3:
        return fail(f"need >=3 implemented properties, got {len(implemented)}")
    if not battery.get("all_pass"):
        bad = [p["id"] for p in implemented if not p.get("pass")]
        return fail(f"properties failed: {bad}")
    for row in implemented:
        if row.get("asserts_model_opinion"):
            return fail(f"{row['id']} asserts model opinion")
        both = row.get("both_states") or {}
        if both.get("known_good_pass", 0) < 1:
            return fail(f"{row['id']} silent on known-good")
        if both.get("known_broken_fail", 0) < 1:
            return fail(f"{row['id']} silent on known-broken")
        if both.get("silent_in_both_states"):
            return fail(f"{row['id']} silent in both states")
        if both.get("known_good_pass") != both.get("trials_good"):
            return fail(f"{row['id']} known-good did not all pass")
        if both.get("known_broken_fail") != both.get("trials_broken"):
            return fail(f"{row['id']} known-broken did not all fail")
        if row["id"] != "P4-counter-monotonicity":
            real = (row.get("real_artifact") or {}).get("result") or {}
            if real.get("pass") is not True:
                return fail(f"{row['id']} failed on real artifact")
    p1 = next(p for p in implemented if p["id"] == "P1-schema-validity")
    if not (p1.get("opinion_control") or {}).get("pass"):
        return fail("FAILED-state control: schema must accept state=FAILED")
    print(
        "real_artifact="
        + str(battery.get("real_artifact"))
        + f" implemented={len(implemented)} untestable={battery.get('untestable_count')}"
    )
    print("SUCCESS:RES-0091-probe1 properties both-states and real artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
