#!/usr/bin/env python3
"""Probe 2: runtime observation (signal B), independent of declared IR.

Replays runtime_script. A planted two-scheduler fusion must fire. A
fusion that declares one scheduler and spawns two must fire here even
though signal A is silent. A benign parallel helper must remain a
helper. Two consistent state-write targets still fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0109-fusion-control-plane-detector.json"
FIX = HERE / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def main() -> int:
    two = D.runtime_observe(load("two-scheduler.json"))
    singular = D.runtime_observe(load("singular.json"))
    helper = D.runtime_observe(load("helper-parallel.json"))
    stores = D.runtime_observe(load("two-state-stores.json"))
    ghost_ir = load("declare-one-spawn-two.json")
    ghost_b = D.runtime_observe(ghost_ir)
    ghost_a = D.static_census(ghost_ir)
    ghost = D.detect(ghost_ir)
    two_full = D.detect(load("two-scheduler.json"))

    print(
        f"two-scheduler B fires={two['fires']} "
        f"procs={two['scheduler_processes']}"
    )
    print(
        f"singular B silent={singular['silent']} "
        f"n_proc={singular['n_scheduler_processes']}"
    )
    print(
        f"helper-parallel B silent={helper['silent']} "
        f"helper_only={helper['helper_only_processes']}"
    )
    print(
        f"two-state-stores B fires={stores['fires']} "
        f"targets={stores['state_write_targets']}"
    )
    print(
        f"declare-one-spawn-two A.fires={ghost_a['fires']} "
        f"B.fires={ghost_b['fires']} diverge={ghost['signals_disagree']} "
        f"procs={ghost_b['scheduler_processes']}"
    )

    checks = [
        (
            two["fires"]
            and "sched-primary" in two["scheduler_processes"]
            and "sched-imported" in two["scheduler_processes"]
            and two_full["fires"]
            and two_full["signal_a"]["fires"]
            and two_full["signal_b"]["fires"],
            "two-scheduler not caught by BOTH signals",
        ),
        (
            singular["silent"] and singular["n_scheduler_processes"] == 1,
            "singular runtime not silent",
        ),
        (
            helper["silent"]
            and helper["n_scheduler_processes"] == 1
            and "helper-west" in helper["helper_only_processes"]
            and "helper-east" in helper["helper_only_processes"]
            and "helper-west" not in helper["scheduler_processes"]
            and "helper-east" not in helper["scheduler_processes"],
            "helper process counted as control plane",
        ),
        (
            stores["fires"]
            and stores["n_state_write_targets"] == 2
            and "store-alpha" in stores["state_write_targets"]
            and "store-beta" in stores["state_write_targets"],
            "two consistent write targets not failed",
        ),
        (
            ghost_a["silent"]
            and ghost_b["fires"]
            and ghost["signals_disagree"] is True
            and "sched-shadow" in ghost_b["scheduler_processes"]
            and ghost["p1_blocks_certification"] is True,
            "declared-one-spawn-two not caught by runtime-only signal",
        ),
        (
            two_full["capability_check"]["ok"] is True,
            "capability check must still pass (duplicate planes both work)",
        ),
    ]
    for ok, why in checks:
        if not ok:
            print(f"FAILED:WFA-0109-probe2 {why}")
            return 1

    if not ART.is_file():
        print("FAILED:WFA-0109-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:WFA-0109" not in text:
        print("FAILED:WFA-0109-probe2 sentinel absent")
        return 1
    cases = {c.get("fusion_id"): c for c in (doc.get("cases") or []) if isinstance(c, dict)}
    rec = cases.get("fx-declare-one-spawn-two") or {}
    if rec.get("signal_a_fires") or not rec.get("signal_b_fires") or not rec.get("signals_disagree"):
        print("FAILED:WFA-0109-probe2 artifact missing divergence case")
        return 1
    if not rec.get("p1_blocks_certification"):
        print("FAILED:WFA-0109-probe2 artifact missing P1 certification block")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe2-runtime-observation",
                "two_scheduler_both_signals": True,
                "helper_not_plane": True,
                "two_stores_fail_despite_consistency": True,
                "declare_one_spawn_two": {
                    "a_fires": ghost_a["fires"],
                    "b_fires": ghost_b["fires"],
                    "disagree": ghost["signals_disagree"],
                    "named": ghost_b["named_planes"],
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0109-probe2 runtime both-signals helper-vs-plane divergence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
