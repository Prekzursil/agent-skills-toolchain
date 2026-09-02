#!/usr/bin/env python3
"""Named probe 2: proven orphan is reaped; allowlist mutation turns probe1 red.

Both-states at the same ceiling fixture:
  * guarded path reaps the two-signal orphan and spares agent-mail
  * emptying the allowlist reaps agent-mail (shared_service_survives is False)
  * a one-signal dead session is not a proven orphan and stays spared
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from resource_guard.termination import (  # noqa: E402
    ACTION_REAP,
    ACTION_SPARE,
    REASON_ORPHAN_NOT_PROVEN,
    REASON_ORPHAN_PROVEN,
    apply_reaps,
    drop_allowlist,
    evaluate,
    health_status,
    load_ceiling_world,
    shared_service_survives,
)

SHARED_PID = 8812
ORPHAN_PID = 9001
LIVE_PID = 9002
ONE_SIGNAL_PID = 9003


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0473-probe2 {msg}")
    return 1


def main() -> int:
    world = load_ceiling_world()
    guarded = evaluate(world)
    if ORPHAN_PID not in guarded.kill_set:
        return fail(f"orphan {ORPHAN_PID} not in kill_set {list(guarded.kill_set)}")
    orphan = guarded.decision_for(ORPHAN_PID)
    if orphan.action != ACTION_REAP or orphan.reason != REASON_ORPHAN_PROVEN:
        return fail(f"orphan decision {orphan.as_dict()}")
    if orphan.orphan.get("signal_count") != 2:
        return fail(f"orphan signal_count={orphan.orphan.get('signal_count')}")
    after_guarded = apply_reaps(world, guarded)
    if after_guarded.process(ORPHAN_PID).alive:
        return fail("orphan still alive after guarded apply_reaps")
    if LIVE_PID in guarded.kill_set:
        return fail("live session worker reaped")
    live = guarded.decision_for(LIVE_PID)
    if live.reason != REASON_ORPHAN_NOT_PROVEN:
        return fail(f"live worker reason={live.reason}")
    one = guarded.decision_for(ONE_SIGNAL_PID)
    if one.action != ACTION_SPARE or one.reason != REASON_ORPHAN_NOT_PROVEN:
        return fail(f"one-signal decision {one.as_dict()}")
    if one.orphan.get("signal_count") != 1:
        return fail("one-signal fixture did not record a single death signal")

    survives_guarded = shared_service_survives(world, guarded, SHARED_PID)
    mutated_world = drop_allowlist(world)
    mutated = evaluate(mutated_world)
    survives_mutated = shared_service_survives(world, mutated, SHARED_PID)
    if not survives_guarded:
        return fail("guarded path already killed the shared service")
    if survives_mutated:
        return fail("allowlist mutation did not turn shared_service_survives red")
    if SHARED_PID not in mutated.kill_set:
        return fail(f"mutated kill_set missing shared pid: {list(mutated.kill_set)}")
    shared_mut = mutated.decision_for(SHARED_PID)
    if shared_mut.reason != REASON_ORPHAN_PROVEN:
        return fail(f"mutated shared reason={shared_mut.reason}")
    if mutated.allowlist_used:
        return fail("drop_allowlist still marked allowlist_used")
    after_mut = apply_reaps(world, mutated)
    health_mut = health_status(after_mut, SHARED_PID)
    if health_mut["ok"]:
        return fail(f"mutated health still ok: {health_mut}")

    # Orphan still reaped under the mutation; live worker still spared.
    if ORPHAN_PID not in mutated.kill_set:
        return fail("mutation lost the orphan reap")
    if LIVE_PID in mutated.kill_set:
        return fail("mutation started killing the live worker")

    payload = {
        "probe": "probe2-orphan-and-allowlist-mutation",
        "unit_id": "IMP-0473",
        "orphan_pid": ORPHAN_PID,
        "orphan_reaped": True,
        "orphan_reason": orphan.reason,
        "orphan_signals": orphan.orphan.get("signals"),
        "one_signal_spared": True,
        "live_worker_spared": True,
        "shared_survives_guarded": survives_guarded,
        "shared_survives_mutated": survives_mutated,
        "first_test_red_under_mutation": (not survives_mutated),
        "mutated_kill_set": list(mutated.kill_set),
        "guarded_kill_set": list(guarded.kill_set),
        "mutated_shared_decision": shared_mut.as_dict(),
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"orphan_reaped={ORPHAN_PID} live_spared={LIVE_PID} "
        f"mutation_kills_shared={SHARED_PID} "
        f"first_test_red_under_mutation={not survives_mutated}"
    )
    print("SUCCESS:IMP-0473-probe2 orphan reaped; allowlist mutation reds survives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
