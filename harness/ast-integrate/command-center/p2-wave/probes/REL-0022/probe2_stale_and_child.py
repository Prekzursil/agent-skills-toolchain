#!/usr/bin/env python3
"""Probe 2: stale inverse, child-process capture, reviewer mutations.

Removing a real side effect while leaving its recorded inverse must fire
the stale-entry direction. Child-process writes must be captured (or the
receipt must declare the region NOT-CHECKED — this probe requires capture).
The reviewer re-runs both mutation controls on fresh profiles.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from canary import create, destroy  # noqa: E402
from coverage import (  # noqa: E402
    CHILD_KEY,
    SKIP_ID,
    STALE_KEY,
    reviewer_mutations,
    run_install,
    subtract,
)
from inverse import recorded_keys  # noqa: E402

ART = REPO / "command-center/receipts/REL-0022.json"


def main() -> int:
    recorded = recorded_keys()
    stale_home = create()
    try:
        stale_obs = run_install(stale_home, skip_id=SKIP_ID)
        stale_sub = subtract(set(stale_obs["effect_keys"]), recorded)
        stale_fired = STALE_KEY in stale_sub["stale_entries"]
    finally:
        destroy(stale_home)
    print(
        f"stale_fired={stale_fired} stale={stale_sub['stale_entries']} "
        f"rc={stale_obs['returncode']}"
    )
    if not stale_fired:
        print("FAILED:REL-0022-probe2 skipped side effect did not fire stale-entry")
        return 1

    child_home = create()
    try:
        child_obs = run_install(child_home)
        child_captured = bool(
            child_obs["child_beacon_in_census"] or CHILD_KEY in child_obs["effect_keys"]
        )
    finally:
        destroy(child_home)
    print(
        f"child_captured={child_captured} "
        f"census={child_obs['child_beacon_in_census']} "
        f"strace_pids={child_obs['strace_child_pids_for_beacon']}"
    )
    if not child_captured:
        print("FAILED:REL-0022-probe2 child-process side effect was not captured")
        return 1

    reviewed = reviewer_mutations()
    print(
        f"reviewer hole_turns_red={reviewed['hole_turns_red']} "
        f"stale_turns_red={reviewed['stale_turns_red']}"
    )
    if not reviewed["pass"]:
        print("FAILED:REL-0022-probe2 reviewer mutations did not both turn red")
        return 1

    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:REL-0022-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:REL-0022-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:REL-0022" not in text:
        print("FAILED:REL-0022-probe2 sentinel absent")
        return 1
    child = doc.get("child_process") or {}
    if not child.get("captured"):
        print("FAILED:REL-0022-probe2 receipt child_process.captured is not true")
        return 1
    if (doc.get("stale_mutation") or {}).get("fired") is not True:
        print("FAILED:REL-0022-probe2 receipt stale_mutation.fired is not true")
        return 1
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("mutations_turn_red") is not True:
        print("FAILED:REL-0022-probe2 receipt reviewer.mutations_turn_red is not true")
        return 1
    if not (doc.get("isolation") or {}).get("fresh_profile_per_attempt"):
        print("FAILED:REL-0022-probe2 isolation.fresh_profile_per_attempt missing")
        return 1

    print("SUCCESS:REL-0022-probe2 stale-entry child-capture reviewer-mutations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
