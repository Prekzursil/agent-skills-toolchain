#!/usr/bin/env python3
"""Probe 1: synthetic commit-charge threshold + live counter rise + spawn.

Catalog tests_required: threshold test with a synthetic commit-charge reading.
Evidence: approach-to-ceiling showing the commit counter rising, the guard
firing, and a process spawn still succeeding after it fired.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from headroom_guard.guard import HeadroomGuard  # noqa: E402
from headroom_guard.ramp import approach_to_ceiling_run  # noqa: E402
from scenario import (  # noqa: E402
    below_threshold,
    commit_headroom_fire,
    commit_high_ram_low,
)

ART = REPO / "command-center/receipts/IMP-0445.json"
SENTINEL = "SENTINEL:IMP-0445:HEADROOM-GUARD-COMMIT-CHARGE"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0445-probe1 {msg}")
    return 1


def main() -> int:
    guard = HeadroomGuard()
    names = set(HeadroomGuard.decide.__code__.co_names)
    ram_names = names & {"ram_percent", "ram_used_bytes", "ram_total_bytes", "ram_used"}
    if ram_names:
        return fail(f"decide() bytecode names include RAM fields {sorted(ram_names)}")
    if "commit_headroom_bytes" not in names and "committed_bytes" not in names:
        return fail(f"decide() bytecode does not name commit-charge fields {sorted(names)}")

    low = below_threshold()
    d_low = guard.decide(current_concurrency=1, requested_concurrency=2, snapshot=low)
    if d_low.fired or not d_low.allow_raise:
        return fail(f"below-threshold unexpectedly fired {d_low.as_dict()}")

    high = commit_high_ram_low()
    d_high = guard.decide(current_concurrency=1, requested_concurrency=2, snapshot=high)
    if not d_high.fired or d_high.allow_raise:
        return fail(f"commit-high did not refuse raise {d_high.as_dict()}")
    if d_high.kill_shared_service:
        return fail("guard-kills-shared-service on threshold fire")
    if d_high.action != "REFUSE_RAISE_CONCURRENCY":
        return fail(f"action={d_high.action}")
    if d_high.counter_read != "Committed_AS/CommitLimit (committed_bytes/commit_limit_bytes)":
        return fail(f"counter_read={d_high.counter_read}")

    # Mutation: raising committed_bytes in the snapshot flips the decision
    # without changing GuardConfig — readout is not derived from the ceiling
    # constant it is meant to check.
    d_mut_low = guard.decide(current_concurrency=4, requested_concurrency=5, snapshot=low)
    d_mut_high = guard.decide(current_concurrency=4, requested_concurrency=5, snapshot=high)
    if d_mut_low.readout["committed_bytes"] == d_mut_high.readout["committed_bytes"]:
        return fail("readout ignored snapshot mutation")
    if d_mut_low.fired or not d_mut_high.fired:
        return fail("snapshot mutation did not flip fire")

    hold = guard.decide(current_concurrency=3, requested_concurrency=3, snapshot=high)
    if not hold.fired or not hold.allow_raise or hold.action != "HOLD_OR_LOWER_ALLOWED":
        return fail(f"fired hold should still allow non-raise {hold.as_dict()}")

    head = commit_headroom_fire()
    d_head = guard.decide(current_concurrency=1, requested_concurrency=2, snapshot=head)
    if "rescue-shell-headroom" not in d_head.reasons:
        return fail(f"headroom trigger missing {d_head.as_dict()}")
    if d_head.allow_raise:
        return fail("headroom fire still allowed a raise")

    run = approach_to_ceiling_run()
    if not run["live_commit_rise"]["counter_rose"]:
        return fail(
            "live Committed_AS did not rise after mmap "
            f"{json.dumps(run['live_commit_rise'], default=str)[:800]}"
        )
    if run["fire_count"] < 1 or run["pre_fire_count"] < 1:
        return fail(f"ramp did not approach then fire {run['pre_fire_count']}/{run['fire_count']}")
    if not run["ram_percent_stayed_uninformative"]:
        return fail("RAM-percent fired on the commit-high/RAM-low ramp (wrong control)")
    if not run["spawn_succeeded_after_fire"]:
        return fail(f"spawn after fire failed {run['spawn_after_fire']}")

    if not ART.is_file() or ART.stat().st_size < 128:
        return fail("receipt artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0445":
        return fail(f"unit_id={doc.get('unit_id')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    out = {
        "probe": "probe1-threshold",
        "unit_id": "IMP-0445",
        "pass": True,
        "counter_read": d_high.counter_read,
        "fired_on_synthetic_commit_high": d_high.fired,
        "refused_raise": not d_high.allow_raise,
        "kill_shared_service": d_high.kill_shared_service,
        "live_committed_delta_bytes": run["live_commit_rise"]["committed_delta_bytes"],
        "first_fire_label": run["first_fire_label"],
        "ram_percent_at_first_fire": run["ram_percent_at_first_fire"],
        "spawn_after_fire": run["spawn_after_fire"],
        "snapshot_mutation_visible_in_readout": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "threshold_fire=True ram_uninformative=True "
        f"spawn_ok={run['spawn_succeeded_after_fire']} "
        f"delta={run['live_commit_rise']['committed_delta_bytes']}"
    )
    print("SUCCESS:IMP-0445-probe1 synthetic commit-charge threshold and spawn-after-fire")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
