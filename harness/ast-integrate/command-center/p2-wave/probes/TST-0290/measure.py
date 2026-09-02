"""Live measurements for TST-0290: three-way stall classification."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from council.owner_ask import build_packet, check_packet  # noqa: E402
from council.simulate import (  # noqa: E402
    FIXED_PID,
    FROZEN_NS,
    SEED_A,
    SEED_B,
    pids_that_reorder,
    simulate,
    three_cast_bundle,
    trace_hash,
)
from council.stopping.deadlock import load_cast, run_three_way  # noqa: E402

OWNER_QUESTION = (
    "Should the council replace a frozen seat on P-CUTOVER rather than "
    "ratifying the split?"
)
OWNER_RECOMMENDATION = (
    "Replace the seed-chosen frozen seat and re-open P-CUTOVER; do not treat "
    "the split as a decision."
)
OWNER_TRADEOFF = (
    "Replacement spends a seat; ratifying the freeze destroys the recorded dissent."
)
OWNER_DEFAULT = (
    "If unanswered, keep P-CUTOVER unresolved and suspend. Do not auto-ratify."
)


def owner_packet() -> dict[str, Any]:
    return build_packet(
        question_id="Q-CUTOVER",
        question=OWNER_QUESTION,
        recommendation=OWNER_RECOMMENDATION,
        strongest_tradeoff=OWNER_TRADEOFF,
        default=OWNER_DEFAULT,
        proposition_id="P-CUTOVER",
    )


def collect() -> dict[str, Any]:
    policy = run_three_way(seed=SEED_A)
    a = three_cast_bundle(seed=SEED_A, clock_ns=FROZEN_NS, pid=FIXED_PID)
    time.sleep(0.002)
    b = three_cast_bundle(seed=SEED_A, clock_ns=FROZEN_NS, pid=FIXED_PID)
    other = three_cast_bundle(seed=SEED_B, clock_ns=FROZEN_NS, pid=FIXED_PID)
    wall = three_cast_bundle(seed=SEED_A, clock_ns=FROZEN_NS + 123456, pid=FIXED_PID)
    live_pid = three_cast_bundle(seed=SEED_A, clock_ns=FROZEN_NS, pid=FIXED_PID + 91)

    leak_clock_frozen = three_cast_bundle(
        seed=SEED_A, clock_ns=FROZEN_NS, pid=FIXED_PID, leak_clock=True
    )
    leak_clock_wall = three_cast_bundle(
        seed=SEED_A, clock_ns=FROZEN_NS + 7, pid=FIXED_PID, leak_clock=True
    )
    seats = load_cast("deadlock")["seats"]
    pid_lo, pid_hi = pids_that_reorder(seats)
    leak_pid_a = simulate("deadlock", seed=SEED_A, pid=pid_lo, leak_pid=True)
    leak_pid_b = simulate("deadlock", seed=SEED_A, pid=pid_hi, leak_pid=True)
    if trace_hash(leak_pid_a) != leak_pid_a["trace_hash"]:
        raise RuntimeError("independent hash mismatch on pid leak a")

    packet = owner_packet()
    two_q = check_packet(
        {
            "questions": [
                "Should we replace the frozen seat?",
                "Should we ratify P-CUTOVER?",
            ],
            "recommendation": OWNER_RECOMMENDATION,
            "strongest_tradeoff": OWNER_TRADEOFF,
            "default": OWNER_DEFAULT,
        }
    )
    settled = check_packet(
        {
            "question_id": "Q-CUTOVER",
            "question": OWNER_QUESTION,
            "recommendation": OWNER_RECOMMENDATION,
            "strongest_tradeoff": OWNER_TRADEOFF,
            "default": OWNER_DEFAULT,
        },
        decision_log=[{"question_id": "Q-CUTOVER"}],
    )
    compound = check_packet(
        {
            "question": (
                "Should we replace the frozen seat, and should we also ratify "
                "the split?"
            ),
            "recommendation": OWNER_RECOMMENDATION,
            "strongest_tradeoff": OWNER_TRADEOFF,
            "default": OWNER_DEFAULT,
        }
    )

    same = a["trace_hash"] == b["trace_hash"]
    seed_moves = a["trace_hash"] != other["trace_hash"]
    frozen_same = a["trace_hash"] == wall["trace_hash"]
    pid_same = a["trace_hash"] == live_pid["trace_hash"]
    clock_leak_fires = leak_clock_frozen["trace_hash"] != leak_clock_wall["trace_hash"]
    pid_leak_fires = leak_pid_a["trace_hash"] != leak_pid_b["trace_hash"]

    sources = [
        {
            "source": "wall-clock",
            "site": "simulate.leak_clock appends leak-clock:{clock_ns} and moves DynamicFanOut",
            "how_found": (
                "Injected FrozenClock vs shifted clock_ns with leak_clock=True; "
                f"hashes {leak_clock_frozen['trace_hash'][:12]} vs "
                f"{leak_clock_wall['trace_hash'][:12]} (differ={clock_leak_fires})."
            ),
            "leaks_into_production_dag": False,
        },
        {
            "source": "pid",
            "site": "simulate.leak_pid reorders due-seat turn nodes",
            "how_found": (
                f"Injected FixedPid({pid_lo}) vs FixedPid({pid_hi}) with "
                f"leak_pid=True; orders differ; hashes differ={pid_leak_fires}."
            ),
            "leaks_into_production_dag": False,
        },
        {
            "source": "seed",
            "site": "DynamicFanOut dyn-replace cardinality = 2 + (seed % 3)",
            "how_found": (
                f"Seed {SEED_A} hash {a['trace_hash'][:12]} vs seed {SEED_B} "
                f"hash {other['trace_hash'][:12]} (diverges={seed_moves})."
            ),
            "leaks_into_production_dag": True,
        },
    ]

    fan_cards = []
    seen = set()
    for row in a["fan_out"]:
        key = (row["id"], row["kind"], row["cardinality"])
        if key in seen:
            continue
        seen.add(key)
        fan_cards.append(
            {
                "id": row["id"],
                "kind": row["kind"],
                "cardinality": row["cardinality"],
            }
        )

    flags = {
        "same_seed_identical": same,
        "different_seed_diverges": seed_moves,
        "frozen_clock_unchanged": frozen_same,
        "fixed_pid_unchanged": pid_same,
        "clock_leak_detector_fired": clock_leak_fires,
        "pid_leak_detector_fired": pid_leak_fires,
        "three_way_ok": policy["ok"],
        "distinct_actions": policy["distinct_actions"],
        "generic_escalation": policy["generic_escalation"],
        "owner_packet_ok": packet["check"]["ok"],
        "two_question_rejected": two_q["ok"] is False,
        "settled_suppressed": settled["ok"] is False,
        "compound_rejected": compound["ok"] is False,
    }
    ok = all(
        [
            flags["same_seed_identical"],
            flags["different_seed_diverges"],
            flags["frozen_clock_unchanged"],
            flags["fixed_pid_unchanged"],
            flags["clock_leak_detector_fired"],
            flags["pid_leak_detector_fired"],
            flags["three_way_ok"],
            flags["distinct_actions"],
            not flags["generic_escalation"],
            flags["owner_packet_ok"],
            flags["two_question_rejected"],
            flags["settled_suppressed"],
            flags["compound_rejected"],
        ]
    )
    return {
        "fan_out_cardinalities": fan_cards,
        "fixed_pid": FIXED_PID,
        "flags": flags,
        "frozen_ns": FROZEN_NS,
        "ok": ok,
        "other_seed": SEED_B,
        "other_seed_hash": other["trace_hash"],
        "owner_packet": packet,
        "owner_negative": {
            "compound": compound,
            "settled": settled,
            "two_questions": two_q,
        },
        "pid_leak_injection": {
            "fired": pid_leak_fires,
            "hash_a": leak_pid_a["trace_hash"],
            "hash_b": leak_pid_b["trace_hash"],
            "node_order_a": leak_pid_a["node_order"],
            "node_order_b": leak_pid_b["node_order"],
            "pid_a": pid_lo,
            "pid_b": pid_hi,
        },
        "clock_leak_injection": {
            "fired": clock_leak_fires,
            "frozen_hash": leak_clock_frozen["trace_hash"],
            "wall_hash": leak_clock_wall["trace_hash"],
        },
        "policy": policy,
        "run_a": {
            "barrier_resolution": a["barrier_resolution"],
            "fan_out": a["fan_out"],
            "node_order": a["node_order"],
            "trace_hash": a["trace_hash"],
        },
        "run_b": {"trace_hash": b["trace_hash"]},
        "seed": SEED_A,
        "sources": sources,
        "three_cast_runs": a["runs"],
        "wall_hash": wall["trace_hash"],
        "live_pid_hash": live_pid["trace_hash"],
    }


def dump() -> int:
    data = collect()
    print(json.dumps({"ok": data["ok"], "flags": data["flags"]}, sort_keys=True))
    return 0 if data["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(dump())
