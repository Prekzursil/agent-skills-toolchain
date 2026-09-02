#!/usr/bin/env python3
"""Property harness for TST-0141: 10_000 randomized 64-taker interleavings.

Any counterexample is shrunk by deleting events until every remaining event
is necessary to reproduce the violation, then replayed.
"""
from __future__ import annotations

import hashlib
import random
import threading
from dataclasses import dataclass
from typing import Any

from token_bucket import Actor, SimBucket, TokenBucket, audit_permits, check_run, execute_schedule

N_INTERLEAVINGS = 10_000
N_TAKERS = 64
DEFAULT_CAPACITY = 8
LIVE_TAKERS = 64
SEED = 141_0141


@dataclass
class RunRecord:
    seed: int
    schedule: list[tuple[str, int]]
    n_takers: int
    capacity: int
    mutant: bool
    result: dict[str, Any]


def generate_and_run(
    rng: random.Random,
    *,
    n_takers: int,
    capacity: int,
    n_refills: int,
    mutant: bool,
) -> RunRecord:
    bucket = SimBucket(capacity=capacity, mutant=mutant)
    actors = [Actor(i) for i in range(n_takers)]
    refill_left = n_refills
    schedule: list[tuple[str, int]] = []
    # Bound retries so a mutant that never "finishes" cannot hang. CAS
    # actors finish in a handful of steps; mutants finish in two.
    safety = n_takers * 32 + n_refills + 8
    while safety > 0:
        safety -= 1
        pending = [a for a in actors if a.pc != 2]
        options: list[tuple[str, int]] = [("step", a.aid) for a in pending]
        if refill_left > 0:
            options.append(("refill", -1))
        if not options:
            break
        kind, idx = options[rng.randrange(len(options))]
        if kind == "refill":
            bucket.refill()
            refill_left -= 1
            schedule.append(("refill", -1))
            continue
        bucket.step(actors[idx])
        schedule.append(("step", idx))
    result = check_run(bucket, actors)
    return RunRecord(
        seed=-1,
        schedule=schedule,
        n_takers=n_takers,
        capacity=capacity,
        mutant=mutant,
        result=result,
    )


def replay(record: RunRecord) -> dict[str, Any]:
    _bucket, _actors, result = execute_schedule(
        record.schedule,
        n_takers=record.n_takers,
        capacity=record.capacity,
        mutant=record.mutant,
    )
    return result


def shrink(record: RunRecord) -> RunRecord:
    """Delete events while the violation still replays. Minimal reproducing schedule."""
    if record.result.get("ok"):
        return record
    schedule = list(record.schedule)
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(schedule):
            candidate = schedule[:i] + schedule[i + 1 :]
            trial = RunRecord(
                seed=record.seed,
                schedule=candidate,
                n_takers=record.n_takers,
                capacity=record.capacity,
                mutant=record.mutant,
                result={},
            )
            trial.result = replay(trial)
            if not trial.result.get("ok"):
                schedule = candidate
                changed = True
                # stay on i: the next event slid into this index
                continue
            i += 1
    out = RunRecord(
        seed=record.seed,
        schedule=schedule,
        n_takers=record.n_takers,
        capacity=record.capacity,
        mutant=record.mutant,
        result={},
    )
    out.result = replay(out)
    return out


def colliding_mutant_schedule() -> RunRecord:
    """Two takers both LOAD capacity=1 then both STORE — over-issue + negative."""
    schedule = [("step", 0), ("step", 1), ("step", 0), ("step", 1)]
    rec = RunRecord(
        seed=0,
        schedule=schedule,
        n_takers=2,
        capacity=1,
        mutant=True,
        result={},
    )
    rec.result = replay(rec)
    return rec


def padded_mutant_schedule() -> RunRecord:
    """Longer colliding run used to prove the shrinker actually shortens."""
    # Takers 2..5 wander in after the race; they are unnecessary for the bug.
    schedule = [
        ("step", 2),  # load extra
        ("step", 0),  # load 0
        ("step", 3),  # load extra
        ("step", 1),  # load 1
        ("step", 0),  # grant 0 (tokens 1 -> 0)
        ("step", 4),  # load extra
        ("step", 1),  # grant 1 (tokens 0 -> -1)
        ("step", 2),  # extra deny/grant leftover
        ("step", 3),
        ("step", 4),
        ("step", 5),
        ("step", 5),
    ]
    rec = RunRecord(
        seed=0,
        schedule=schedule,
        n_takers=6,
        capacity=1,
        mutant=True,
        result={},
    )
    rec.result = replay(rec)
    return rec


def run_property_suite(n: int = N_INTERLEAVINGS, seed: int = SEED) -> dict[str, Any]:
    rng = random.Random(seed)
    failures: list[dict[str, Any]] = []
    granted_hist: dict[int, int] = {}
    for i in range(n):
        if i < 8000:
            n_takers, capacity, n_refills = N_TAKERS, DEFAULT_CAPACITY, 0
        elif i < 9000:
            n_takers, capacity, n_refills = N_TAKERS, 1, 0
        else:
            n_takers, capacity, n_refills = N_TAKERS, DEFAULT_CAPACITY, 1 + (i % 2)
        rec = generate_and_run(
            rng,
            n_takers=n_takers,
            capacity=capacity,
            n_refills=n_refills,
            mutant=False,
        )
        rec.seed = seed + i
        g = int(rec.result["granted"])
        granted_hist[g] = granted_hist.get(g, 0) + 1
        if not rec.result["ok"]:
            shrunk = shrink(rec)
            replayed = replay(shrunk)
            failures.append(
                {
                    "index": i,
                    "seed": rec.seed,
                    "n_takers": n_takers,
                    "capacity": capacity,
                    "n_refills": n_refills,
                    "violations": rec.result["violations"],
                    "schedule_len": len(rec.schedule),
                    "shrunk_len": len(shrunk.schedule),
                    "shrunk_replay_ok": replayed.get("ok"),
                    "shrunk_schedule": shrunk.schedule[:40],
                }
            )
            break
    return {
        "ok": not failures,
        "n": n,
        "seed": seed,
        "n_takers": N_TAKERS,
        "failures": failures,
        "granted_histogram": {str(k): v for k, v in sorted(granted_hist.items())},
        "runs_completed": n if not failures else failures[0]["index"] + 1,
    }


def run_mutation_control() -> dict[str, Any]:
    crafted = colliding_mutant_schedule()
    padded = padded_mutant_schedule()
    shrunk = shrink(padded)
    replayed = replay(shrunk)
    # Same colliding schedule on the CAS bucket must be clean.
    cas = RunRecord(
        seed=0,
        schedule=crafted.schedule,
        n_takers=2,
        capacity=1,
        mutant=False,
        result={},
    )
    cas.result = replay(cas)
    return {
        "ok": (
            (not crafted.result["ok"])
            and (not padded.result["ok"])
            and (not shrunk.result["ok"])
            and (not replayed["ok"])
            and cas.result["ok"]
            and len(shrunk.schedule) < len(padded.schedule)
            and len(shrunk.schedule) >= 4
        ),
        "crafted_violations": crafted.result["violations"],
        "crafted_tokens": crafted.result["tokens"],
        "crafted_granted": crafted.result["granted"],
        "crafted_audit": crafted.result["external_audit"],
        "padded_len": len(padded.schedule),
        "shrunk_len": len(shrunk.schedule),
        "shrunk_schedule": shrunk.schedule,
        "shrunk_violations": shrunk.result["violations"],
        "shrunk_replay_ok": replayed["ok"],
        "cas_control_ok": cas.result["ok"],
        "cas_granted": cas.result["granted"],
        "cas_tokens": cas.result["tokens"],
    }


def run_live_threads(
    n_takers: int = LIVE_TAKERS,
    capacity: int = DEFAULT_CAPACITY,
    *,
    atomic: bool = True,
) -> dict[str, Any]:
    bucket = TokenBucket(capacity, atomic=atomic)
    granted: list[bool] = [False] * n_takers
    errors: list[str] = []

    def worker(i: int) -> None:
        try:
            granted[i] = bucket.take(1, taker_id=i)
        except Exception as exc:  # noqa: BLE001 — record, do not swallow
            errors.append(f"taker {i}: {type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_takers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    log = bucket.permit_dicts()
    external = audit_permits(log, capacity)
    n_granted = sum(1 for g in granted if g)
    tokens = bucket.tokens()
    violations: list[str] = []
    if tokens < 0:
        violations.append(f"negative:{tokens}")
    if n_granted > capacity:
        violations.append(f"over_issue:{n_granted}>{capacity}")
    if not external["ok"]:
        violations.append(f"audit:{external['over_capacity_windows']}")
    if errors:
        violations.append("exceptions:" + errors[0])
    if bucket.invariant_trips:
        violations.append("internal:" + bucket.invariant_trips[0])
    return {
        "ok": not violations,
        "atomic": atomic,
        "n_takers": n_takers,
        "capacity": capacity,
        "granted": n_granted,
        "tokens": tokens,
        "external_audit": external,
        "internal_trips": list(bucket.invariant_trips),
        "violations": violations,
        "errors": errors,
        "permit_log": log,
    }


def fingerprint_schedule(schedule: list[tuple[str, int]]) -> str:
    blob = repr(schedule).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def run_all() -> dict[str, Any]:
    prop = run_property_suite()
    mut = run_mutation_control()
    live = run_live_threads(atomic=True)
    return {
        "ok": bool(prop["ok"] and mut["ok"] and live["ok"]),
        "property": prop,
        "mutation": mut,
        "live_threads": {
            k: v for k, v in live.items() if k != "permit_log"
        },
        "live_permit_log": live["permit_log"],
    }
