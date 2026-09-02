#!/usr/bin/env python3
"""Live measurements for TST-0029: seed-stable DAG trace + clock/PID injection."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from load_lib import ensure_import, repo

ensure_import()
from agentspec.clock import FixedPid, FrozenClock, Host, LivePid, frozen_host, wall_host
from agentspec.replay import ready_sort_key, replay_workflow
from agentspec.scan import scan_file, scan_paths

HERE = Path(__file__).resolve().parent
REPO = repo()
FIXTURES = HERE / "fixtures"
SEEDED = FIXTURES / "wf.seeded-dag.json"
PLANTED = FIXTURES / "wf.date-now-banned.json"
SEED_A = 7
SEED_B = 8
FROZEN_NS = 0
FIXED_PID = 4242


def load_seeded() -> dict[str, Any]:
    return json.loads(SEEDED.read_text(encoding="utf-8"))


def independent_hash(trace: dict[str, Any]) -> str:
    """Second encoding of the structural trace; must match the library digest."""
    payload = {
        "barrier_resolution": trace["barrier_resolution"],
        "fan_out": trace["fan_out"],
        "node_order": trace["node_order"],
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    import hashlib

    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def pids_that_reorder(ids: list[str], limit: int = 8000) -> tuple[int, int, list[str], list[str]]:
    def order_for(pid: int) -> list[str]:
        host = frozen_host(SEED_A, pid=pid, leak_pid_into_ready=True)
        return sorted(ids, key=lambda n: ready_sort_key(n, host))

    first_pid = 1
    first_order = order_for(first_pid)
    for pid in range(2, limit + 1):
        order = order_for(pid)
        if order != first_order:
            return first_pid, pid, list(first_order), order
    raise RuntimeError(f"no pid pair reordered {ids}")


def run(
    wf: dict[str, Any],
    *,
    seed: int,
    clock: str,
    pid: int | None,
    leak_clock: bool = False,
    leak_pid: bool = False,
) -> dict[str, Any]:
    if clock == "frozen":
        host = frozen_host(
            seed,
            clock_ns=FROZEN_NS,
            pid=FIXED_PID if pid is None else pid,
            leak_clock_into_fanout=leak_clock,
            leak_pid_into_ready=leak_pid,
        )
    elif clock == "wall":
        host = wall_host(
            seed,
            pid=LivePid() if pid is None else FixedPid(pid),
            leak_clock_into_fanout=leak_clock,
            leak_pid_into_ready=leak_pid,
        )
    else:
        raise ValueError(clock)
    result = replay_workflow(wf, host)
    lib_hash = result["trace_hash"]
    indep = independent_hash(result["trace"])
    if lib_hash != indep:
        raise RuntimeError(f"library hash {lib_hash} != independent hash {indep}")
    return result


def collect() -> dict[str, Any]:
    wf = load_seeded()
    a = run(wf, seed=SEED_A, clock="frozen", pid=FIXED_PID)
    time.sleep(0.002)
    b = run(wf, seed=SEED_A, clock="frozen", pid=FIXED_PID)
    other = run(wf, seed=SEED_B, clock="frozen", pid=FIXED_PID)
    wall = run(wf, seed=SEED_A, clock="wall", pid=FIXED_PID)
    time.sleep(0.002)
    wall2 = run(wf, seed=SEED_A, clock="wall", pid=FIXED_PID)
    live = replay_workflow(
        wf,
        Host(
            clock=FrozenClock(FROZEN_NS),
            pid=LivePid(),
            seed=SEED_A,
        ),
    )
    if independent_hash(live["trace"]) != live["trace_hash"]:
        raise RuntimeError("live pid independent hash mismatch")

    leak_clock_frozen = run(
        wf, seed=SEED_A, clock="frozen", pid=FIXED_PID, leak_clock=True
    )
    leak_clock_wall = run(
        wf, seed=SEED_A, clock="wall", pid=FIXED_PID, leak_clock=True
    )
    ready_ids = ["fan-ab", "producer"]
    pid_lo, pid_hi, order_lo, order_hi = pids_that_reorder(ready_ids)
    leak_pid_a = run(
        wf, seed=SEED_A, clock="frozen", pid=pid_lo, leak_pid=True
    )
    leak_pid_b = run(
        wf, seed=SEED_A, clock="frozen", pid=pid_hi, leak_pid=True
    )

    planted_hits = scan_file(PLANTED, repo=REPO)
    clean_hits = scan_file(SEEDED, repo=REPO)
    executor_hits = scan_paths(
        [
            REPO / "tools" / "agentspec" / "agentspec" / "replay.py",
            REPO / "tools" / "agentspec" / "agentspec" / "canonical_trace.py",
            REPO / "tools" / "workflow_foundry" / "replay.py",
        ],
        repo=REPO,
    )
    clock_module_hits = scan_file(
        REPO / "tools" / "agentspec" / "agentspec" / "clock.py", repo=REPO
    )
    confirmation_runner_hits = scan_file(
        REPO / "command-center" / "p2-wave" / "probes" / "CNF-0074" / "runner.py",
        repo=REPO,
    )

    same = a["trace_hash"] == b["trace_hash"]
    seed_moves = a["trace_hash"] != other["trace_hash"]
    frozen_same = a["trace_hash"] == wall["trace_hash"] == wall2["trace_hash"]
    pid_same = a["trace_hash"] == live["trace_hash"]
    clock_leak_fires = leak_clock_frozen["trace_hash"] != leak_clock_wall["trace_hash"]
    pid_leak_fires = leak_pid_a["trace_hash"] != leak_pid_b["trace_hash"]
    planted_clock = [h for h in planted_hits if h.get("kind") == "wall-clock"]
    clean_banned = list(clean_hits)
    exec_banned = list(executor_hits)

    sources = [
        {
            "source": "wall-clock",
            "site": "DynamicFanOut.cardinality+child-ids when leak_clock_into_fanout",
            "how_found": (
                "Injected FrozenClock(0) vs WallClock with leak_clock_into_fanout=True; "
                f"hashes {leak_clock_frozen['trace_hash'][:12]} vs "
                f"{leak_clock_wall['trace_hash'][:12]} (differ={clock_leak_fires})."
            ),
            "leaks_into_production_dag": False,
        },
        {
            "source": "pid",
            "site": "ready-set order when leak_pid_into_ready",
            "how_found": (
                f"Injected FixedPid({pid_lo}) vs FixedPid({pid_hi}) with "
                f"leak_pid_into_ready=True; orders {order_lo} vs {order_hi}; "
                f"hashes differ={pid_leak_fires}."
            ),
            "leaks_into_production_dag": False,
        },
        {
            "source": "wall-clock",
            "site": str(PLANTED.relative_to(REPO).as_posix()),
            "how_found": (
                "Static scan of a planted saved workflow containing Date.now(); "
                f"hits={len(planted_clock)}."
            ),
            "leaks_into_production_dag": False,
        },
    ]
    if confirmation_runner_hits:
        sources.append(
            {
                "source": "wall-clock",
                "site": "command-center/p2-wave/probes/CNF-0074/runner.py",
                "how_found": (
                    "Static scan of the CNF-0074 confirmation runner (stamp-time / "
                    f"unseeded-sample / cache-off). hits={len(confirmation_runner_hits)}. "
                    "Not the Phase-7 agentspec DAG executor."
                ),
                "leaks_into_production_dag": False,
            }
        )

    fan_cards = [
        {"id": row["id"], "kind": row["kind"], "cardinality": row["cardinality"]}
        for row in a["trace"]["fan_out"]
    ]
    return {
        "seed": SEED_A,
        "other_seed": SEED_B,
        "same_seed_identical": same,
        "different_seed_diverges": seed_moves,
        "run_a": {
            "trace_hash": a["trace_hash"],
            "node_order": a["trace"]["node_order"],
            "fan_out": a["trace"]["fan_out"],
            "barrier_resolution": a["trace"]["barrier_resolution"],
            "steps": a["steps"],
        },
        "run_b": {"trace_hash": b["trace_hash"]},
        "other_seed_hash": other["trace_hash"],
        "frozen_vs_wall": {
            "frozen_hash": a["trace_hash"],
            "wall_hash": wall["trace_hash"],
            "wall_hash_repeat": wall2["trace_hash"],
            "identical": frozen_same,
        },
        "fixed_vs_live_pid": {
            "fixed_pid": FIXED_PID,
            "fixed_hash": a["trace_hash"],
            "live_hash": live["trace_hash"],
            "identical": pid_same,
        },
        "clock_leak_injection": {
            "frozen_hash": leak_clock_frozen["trace_hash"],
            "wall_hash": leak_clock_wall["trace_hash"],
            "fired": clock_leak_fires,
            "frozen_cardinality": leak_clock_frozen["trace"]["fan_out"],
            "wall_cardinality": leak_clock_wall["trace"]["fan_out"],
        },
        "pid_leak_injection": {
            "pid_a": pid_lo,
            "pid_b": pid_hi,
            "order_a": order_lo,
            "order_b": order_hi,
            "hash_a": leak_pid_a["trace_hash"],
            "hash_b": leak_pid_b["trace_hash"],
            "fired": pid_leak_fires,
            "node_order_a": leak_pid_a["trace"]["node_order"],
            "node_order_b": leak_pid_b["trace"]["node_order"],
        },
        "banned_scan": {
            "planted": planted_hits,
            "clean_fixture": clean_hits,
            "executor": executor_hits,
            "clock_module": clock_module_hits,
            "cnf0074_runner": confirmation_runner_hits,
        },
        "fan_out_cardinalities": fan_cards,
        "sources": sources,
        "ok": bool(
            same
            and seed_moves
            and frozen_same
            and pid_same
            and clock_leak_fires
            and pid_leak_fires
            and planted_clock
            and not clean_banned
            and not exec_banned
        ),
        "flags": {
            "same_seed_identical": same,
            "different_seed_diverges": seed_moves,
            "frozen_clock_unchanged": frozen_same,
            "fixed_pid_unchanged": pid_same,
            "clock_leak_detector_fired": clock_leak_fires,
            "pid_leak_detector_fired": pid_leak_fires,
            "planted_date_now_detected": bool(planted_clock),
            "clean_fixture_clean": not clean_banned,
            "executor_source_clean": not exec_banned,
        },
    }
