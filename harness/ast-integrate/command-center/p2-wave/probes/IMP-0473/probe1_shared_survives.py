#!/usr/bin/env python3
"""Named probe 1: shared service survives a ceiling-pressure run.

agent-mail is present, commit-charge is at the ceiling, RAM-percent would
not have fired. The per-candidate decision record must show why the
shared service was spared (ALLOWLIST_PROTECTED). Health stays 200.
Below-ceiling control: nobody is reaped.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from resource_guard.termination import (  # noqa: E402
    ACTION_SPARE,
    REASON_ALLOWLIST,
    REASON_BELOW_CEILING,
    apply_reaps,
    evaluate,
    health_status,
    load_below_ceiling_world,
    load_ceiling_world,
    naive_rss_kill_set,
    shared_service_survives,
)

SHARED_PID = 8812
LIVE_PID = 9002


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0473-probe1 {msg}")
    return 1


def main() -> int:
    world = load_ceiling_world()
    if not world.at_ceiling():
        return fail("fixture is not at the commit-charge ceiling")
    run = evaluate(world)
    if run.ram_percent_would_fire:
        return fail("RAM-percent would have fired; fixture must keep it uninformative")
    if run.ram_percent >= run.commit_ceiling:
        return fail("ram_percent is not below the ceiling constant")
    if SHARED_PID in run.kill_set:
        return fail(f"shared service pid {SHARED_PID} is in kill_set {list(run.kill_set)}")
    if not shared_service_survives(world, run, SHARED_PID):
        return fail("shared_service_survives returned False at the ceiling")
    decision = run.decision_for(SHARED_PID)
    if decision.action != ACTION_SPARE:
        return fail(f"shared service action={decision.action}")
    if decision.reason != REASON_ALLOWLIST:
        return fail(f"shared service reason={decision.reason}, want ALLOWLIST_PROTECTED")
    if not decision.allowlist_match:
        return fail("decision did not record how the allowlist matched")
    after = apply_reaps(world, run)
    health = health_status(after, SHARED_PID)
    if not health["ok"] or health["code"] != 200:
        return fail(f"health after ceiling run: {health}")
    if after.process(SHARED_PID).alive is not True:
        return fail("shared service marked not-alive after apply_reaps")

    naive = naive_rss_kill_set(world, n=1)
    if naive == (SHARED_PID,):
        return fail("fixture: shared service is also the RSS-max process")
    if LIVE_PID in run.kill_set:
        return fail("live session worker was reaped")

    below = load_below_ceiling_world()
    below_run = evaluate(below)
    if below_run.kill_set:
        return fail(f"below-ceiling kill_set={list(below_run.kill_set)}")
    for row in below_run.decisions:
        if row.reason != REASON_BELOW_CEILING:
            return fail(f"below-ceiling reason={row.reason} pid={row.pid}")

    payload = {
        "probe": "probe1-shared-service-survives",
        "unit_id": "IMP-0473",
        "at_ceiling": run.at_ceiling,
        "commit_charge": run.commit_charge,
        "commit_ceiling": run.commit_ceiling,
        "ram_percent": run.ram_percent,
        "ram_percent_would_fire": run.ram_percent_would_fire,
        "shared_pid": SHARED_PID,
        "kill_set": list(run.kill_set),
        "shared_spared": True,
        "shared_reason": decision.reason,
        "allowlist_match": decision.allowlist_match,
        "health": health,
        "naive_rss_kill_set": list(naive),
        "below_ceiling_kill_set": list(below_run.kill_set),
        "decision": decision.as_dict(),
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"shared_pid={SHARED_PID} spared reason={decision.reason} "
        f"match={decision.allowlist_match} health={health['code']} "
        f"kill_set={list(run.kill_set)}"
    )
    print("SUCCESS:IMP-0473-probe1 shared service survives at the ceiling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
