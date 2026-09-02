#!/usr/bin/env python3
"""Assemble the measured ARC-0110 payload (no artifact I/O)."""
from __future__ import annotations

from typing import Any

import both_states as B
import ceremony as C
import inventory as I

QUESTION = (
    "Execute the freeze the spec requires once the first implementation wave "
    "starts: hash every schema and launcher, record the frozen set, and arm "
    "the gate that REJECTS a change to a frozen artifact arriving without a "
    "versioned migration record. Determine the exact trigger moment for the "
    "freeze and what remains editable after it."
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0110/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0110/probe2_scope.py"
)

NAMED_CONTRACTS = (
    "command-center/phase4/contracts/ARC-0092.json",
    "command-center/phase4/contracts/ARC-0093.json",
)


def fingerprint(census: dict[str, Any], demo: dict[str, Any]) -> dict[str, Any]:
    states = demo["states"]
    return {
        "set_sha256": census["set_sha256"],
        "frozen_count": census["frozen_count"],
        "schema_count": census["schema_count"],
        "launcher_count": census["launcher_count"],
        "both_states_pass": bool(demo["both_states_pass"]),
        "unmigrated_rejects": bool(states["unmigrated_rejects"]),
        "migrated_accepts": bool(states["migrated_accepts"]),
        "nonfrozen_silent": bool(states["nonfrozen_silent"]),
        "clean_silent": bool(states["clean_silent"]),
        "detector_control_fired": bool(demo["detector_control"]["fired"]),
        "trigger_id": C.TRIGGER_ID,
        "git_checkout_not_used": bool(demo["git_checkout_not_used"]),
        "not_frozen_example_count": len(census["not_frozen"]["examples"]),
        "named_contracts_present": sum(
            1 for rel in NAMED_CONTRACTS if (I.REPO / rel).is_file()
        ),
    }


def measured() -> dict[str, Any]:
    census = I.census()
    if census["schema_count"] < 1 or census["launcher_count"] < 1:
        raise RuntimeError(
            "freeze set empty: "
            f"schemas={census['schema_count']} launchers={census['launcher_count']}"
        )
    if census["not_frozen_examples_missing"]:
        raise RuntimeError(
            "not-frozen examples missing: "
            + ",".join(census["not_frozen_examples_missing"])
        )
    if census["not_frozen_examples_overclassed"]:
        raise RuntimeError(
            "not-frozen examples classified frozen: "
            + ",".join(census["not_frozen_examples_overclassed"])
        )
    demo = B.run(I.REPO)
    control = demo["detector_control"]
    if not control.get("trusted"):
        raise RuntimeError(
            "detector control not trusted; refusing to record a silent freeze "
            f"fired={control.get('fired')} clean_silent={control.get('clean_silent')}"
        )
    if not demo.get("both_states_pass"):
        raise RuntimeError(f"both-states failed: {demo.get('states')}")
    armed_at = C.now_utc()
    trig = C.trigger(armed_at=armed_at, set_sha256=census["set_sha256"])
    fp = fingerprint(census, demo)
    return {
        "question": QUESTION,
        "probe_commands": {"probe1": P1, "probe2": P2},
        "census": census,
        "both_states": demo,
        "trigger": trig,
        "fingerprint": fp,
        "named_contracts": [
            {"path": rel, "present": (I.REPO / rel).is_file()}
            for rel in NAMED_CONTRACTS
        ],
        "answers": {
            "trigger_moment": trig["predicate"],
            "trigger_id": trig["id"],
            "frozen_count": census["frozen_count"],
            "editable_after": trig["editable_after"],
            "gate_rejects_unmigrated": fp["unmigrated_rejects"],
            "gate_accepts_migrated": fp["migrated_accepts"],
            "gate_silent_on_not_frozen": fp["nonfrozen_silent"],
            "named_phase4_contracts_arc0092_arc0093_present": fp[
                "named_contracts_present"
            ],
        },
    }
