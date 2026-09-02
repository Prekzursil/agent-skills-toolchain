#!/usr/bin/env python3
"""Discrete-event arrival scheduler under test for TST-0321.

B07 phase-9 tools.dispatch is a capability-mismatch dispatcher (IMP-0423).
It has no admission stagger, token bucket, worker queue, or shed path.
This module is the arrival/queue scheduler the 10x question measures:
stub workers with scripted latency, simulated time, named backpressure,
and a provider 429 bucket (failure class :11318).
"""
from __future__ import annotations

import heapq
import os
import resource
import socket
from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable

PLANNED_UNITS = 2048
PLANNED_RATE = 8.0
MULTS = (1.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0)
FC_11318 = "FC-11318-429-arrival-rate-storm"
OWNER_HOST_MARKERS = ("owner-workstation", "owner-desktop")


class LocalStabilityError(RuntimeError):
    """Full-rate wall-clock on a forbidden substrate."""


@dataclass(frozen=True)
class Config:
    planned_rate: float = PLANNED_RATE
    planned_units: int = PLANNED_UNITS
    worker_count: int = 4
    worker_latency: float = 0.4
    bucket_capacity: float = 16.0
    bucket_refill: float = PLANNED_RATE
    stagger_window: float = 2.0
    max_worker_queue: int = 32
    max_retries: int = 6
    retry_after: float = 0.5
    silent_drop: bool = False
    clock: str = "simulated"


PROVIDER_BIND = Config()
WORKER_BIND = Config(
    worker_count=1,
    worker_latency=1.0,
    bucket_capacity=10_000.0,
    bucket_refill=10_000.0,
    stagger_window=1_000.0,
    max_worker_queue=4,
)


def is_owner_workstation() -> bool:
    flag = os.environ.get("TST0321_OWNER_WORKSTATION", "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    host = socket.gethostname().lower()
    return any(marker in host for marker in OWNER_HOST_MARKERS)


def wallclock_fullrate_allowed() -> bool:
    return os.environ.get("TST0321_ALLOW_WALLCLOCK", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def assert_local_stability(offered_mult: float, clock: str) -> dict[str, Any]:
    owner = is_owner_workstation()
    record = {
        "owner_workstation": owner,
        "hostname": socket.gethostname(),
        "os": os.uname().sysname,
        "clock": clock,
        "offered_mult": offered_mult,
        "catalog_substrate": "cloud-batch",
        "actually_used": "linux-worktree-isolated-simulated-time-stub-workers",
        "full_rate_wallclock_executed": False,
        "full_rate_wallclock_refused": False,
        "refuse_reason": None,
    }
    if clock == "wall" and offered_mult >= 10.0:
        if owner or not wallclock_fullrate_allowed():
            record["full_rate_wallclock_refused"] = True
            record["refuse_reason"] = (
                "local-stability-guard: 10x wall-clock admission is forbidden "
                "on the owner workstation and, unless TST0321_ALLOW_WALLCLOCK=1, "
                "on this worktree too. Use simulated time and stub workers."
            )
            raise LocalStabilityError(record["refuse_reason"])
        record["full_rate_wallclock_executed"] = True
        record["actually_used"] = "wall-clock-full-rate"
    return record


def dispatch_layer_inventory() -> dict[str, Any]:
    try:
        import tools.dispatch as layer  # type: ignore
    except Exception as exc:  # pragma: no cover
        return {"present": False, "error": type(exc).__name__}
    names = list(getattr(layer, "__all__", []))
    return {
        "present": True,
        "module": "tools.dispatch",
        "exports": names,
        "has_admit": hasattr(layer, "admit"),
        "has_stagger": hasattr(layer, "stagger"),
        "has_token_bucket": hasattr(layer, "token_bucket"),
        "role": (
            "capability-mismatch degrade-loudly (IMP-0423); "
            "not an arrival-rate / queue scheduler"
        ),
    }


def _pct(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    idx = int(round((p / 100.0) * (len(ys) - 1)))
    idx = min(max(idx, 0), len(ys) - 1)
    return ys[idx]


def _rss_kb() -> int:
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def offer_train(
    n: int,
    mult: float,
    planned_rate: float = PLANNED_RATE,
    *,
    phase: int = 0,
    start_id: int = 0,
) -> list[tuple[float, int, int]]:
    rate = mult * planned_rate
    if rate <= 0:
        raise ValueError("offered rate must be positive")
    return [(i / rate, start_id + i, phase) for i in range(n)]


def classify(summary: dict[str, Any]) -> str | None:
    if int(summary.get("n_unaccounted") or 0) > 0:
        return "silent-drop"
    if int(summary.get("n_429") or 0) > 0 or int(summary.get("n_exhausted") or 0) > 0:
        return FC_11318
    if int(summary.get("n_shed") or 0) > 0:
        return "named-shed-queue-full"
    offered = float(summary.get("offered_rate") or 0.0)
    completed = float(summary.get("completed_rate") or 0.0)
    if offered > 0 and completed < 0.85 * offered:
        return "throughput-collapse"
    if int(summary.get("n_collapse") or 0) > 0:
        return "stagger-window-collapse"
    return None


def simulate(
    offers: Iterable[tuple[float, int, int]], cfg: Config | None = None
) -> dict[str, Any]:
    cfg = cfg or PROVIDER_BIND
    if cfg.clock != "simulated":
        assert_local_stability(10.0, cfg.clock)

    heap: list[tuple[float, int, str, int, dict[str, Any] | None]] = []
    seq = 0

    def push(t: float, kind: str, uid: int, extra: dict[str, Any] | None = None) -> None:
        nonlocal seq
        seq += 1
        heapq.heappush(heap, (t, seq, kind, uid, extra))

    offer_list = list(offers)
    for t, uid, phase in offer_list:
        push(float(t), "offer", int(uid), {"phase": int(phase)})

    tokens = cfg.bucket_capacity
    last_t = 0.0
    last_slot = -1.0 / cfg.planned_rate
    idle = cfg.worker_count
    wait_q: deque[int] = deque()
    ledger: dict[int, dict[str, Any]] = {}
    unaccounted = 0
    n_429 = 0
    n_shed = 0
    n_collapse = 0
    max_worker_q = 0
    stagger_pending = 0
    max_stagger_q = 0

    def update_tokens(t: float) -> None:
        nonlocal tokens, last_t
        dt = max(0.0, t - last_t)
        tokens = min(cfg.bucket_capacity, tokens + dt * cfg.bucket_refill)
        last_t = t

    def latency(uid: int) -> float:
        return cfg.worker_latency * (1.0 + 0.1 * (uid % 5))

    def account(uid: int, **fields: Any) -> dict[str, Any]:
        row = ledger.setdefault(uid, {"unit_id": uid})
        row.update(fields)
        return row

    def start_work(t: float, uid: int) -> None:
        nonlocal idle
        idle -= 1
        lat = latency(uid)
        account(uid, disposition="running", start_t=t, worker_latency=lat)
        push(t + lat, "complete", uid, None)

    def try_dispatch(t: float, uid: int) -> None:
        nonlocal n_shed, unaccounted
        if idle > 0:
            start_work(t, uid)
            return
        if len(wait_q) < cfg.max_worker_queue:
            wait_q.append(uid)
            account(uid, disposition="queued-worker", queued_t=t)
            return
        if cfg.silent_drop:
            unaccounted += 1
            ledger.pop(uid, None)
            return
        n_shed += 1
        account(
            uid,
            disposition="shed-queue-full",
            shed_t=t,
            reason="worker-queue-full",
        )

    def try_admit(t: float, uid: int) -> None:
        nonlocal tokens, n_429
        update_tokens(t)
        row = ledger.get(uid) or account(uid)
        if tokens >= 1.0:
            tokens -= 1.0
            account(uid, admit_t=t, tokens_after=round(tokens, 6))
            try_dispatch(t, uid)
            return
        n_429 += 1
        retries = int(row.get("retries") or 0) + 1
        account(
            uid,
            last_429_t=t,
            retries=retries,
            disposition="rate-limited-429",
            reason=FC_11318,
        )
        if retries > cfg.max_retries:
            account(uid, disposition="rate-limited-exhausted", exhausted_t=t)
        else:
            push(t + cfg.retry_after, "retry", uid, None)

    while heap:
        t, _, kind, uid, extra = heapq.heappop(heap)
        max_worker_q = max(max_worker_q, len(wait_q))
        max_stagger_q = max(max_stagger_q, stagger_pending)
        if kind == "offer":
            account(
                uid,
                offer_t=t,
                phase=(extra or {}).get("phase", 0),
                disposition="offered",
            )
            desired = max(t, last_slot + (1.0 / cfg.planned_rate))
            delay = desired - t
            if delay > cfg.stagger_window:
                n_collapse += 1
                desired = t
                last_slot = t
                account(uid, stagger_collapse=True)
            else:
                last_slot = desired
            if desired <= t:
                try_admit(t, uid)
            else:
                stagger_pending += 1
                account(uid, disposition="queued-stagger", admit_at=desired)
                push(desired, "admit", uid, None)
        elif kind == "admit":
            stagger_pending = max(0, stagger_pending - 1)
            try_admit(t, uid)
        elif kind == "retry":
            try_admit(t, uid)
        elif kind == "complete":
            idle += 1
            account(uid, disposition="completed", complete_t=t)
            if wait_q:
                nxt = wait_q.popleft()
                start_work(t, nxt)

    n_offered = len(offer_list)
    n_completed = sum(1 for r in ledger.values() if r.get("disposition") == "completed")
    n_exhausted = sum(
        1 for r in ledger.values() if r.get("disposition") == "rate-limited-exhausted"
    )
    n_shed_rows = sum(
        1 for r in ledger.values() if r.get("disposition") == "shed-queue-full"
    )
    offer_ts = [t for t, _, _ in offer_list]
    complete_ts = [
        float(r["complete_t"]) for r in ledger.values() if "complete_t" in r
    ]
    admit_lat = [
        float(r["admit_t"]) - float(r["offer_t"])
        for r in ledger.values()
        if "offer_t" in r and "admit_t" in r
    ]
    first_offer = min(offer_ts) if offer_ts else 0.0
    last_offer = max(offer_ts) if offer_ts else 0.0
    last_event = last_t
    if complete_ts:
        last_event = max(last_event, max(complete_ts))
    duration = max(last_event - first_offer, 1e-9)
    offer_span = max(last_offer - first_offer, 1e-9)
    offered_rate = (
        (n_offered - 1) / offer_span if n_offered > 1 else cfg.planned_rate
    )
    completed_rate = n_completed / duration
    terminal = n_completed + n_shed_rows + n_exhausted
    invariant_ok = (n_offered == terminal + unaccounted) and (n_shed_rows == n_shed)

    summary = {
        "n_offered": n_offered,
        "n_completed": n_completed,
        "n_429": n_429,
        "n_shed": n_shed,
        "n_exhausted": n_exhausted,
        "n_unaccounted": unaccounted,
        "n_collapse": n_collapse,
        "n_ledger": len(ledger),
        "max_worker_queue_depth": max_worker_q,
        "max_stagger_queue_depth": max_stagger_q,
        "offered_rate": round(offered_rate, 6),
        "completed_rate": round(completed_rate, 6),
        "scheduler_latency_p50": _pct(admit_lat, 50),
        "scheduler_latency_p95": _pct(admit_lat, 95),
        "sim_duration": round(duration, 6),
        "rss_kb": _rss_kb(),
        "clock": cfg.clock,
        "worker_count": cfg.worker_count,
        "planned_rate": cfg.planned_rate,
        "bucket_refill": cfg.bucket_refill,
        "stagger_window": cfg.stagger_window,
        "silent_drop": cfg.silent_drop,
        "invariant_ok": invariant_ok,
        "terminal": terminal,
    }
    summary["failure_mode"] = classify(summary)
    return summary


def saturation_curve(
    n_per_point: int = 512, cfg: Config | None = None
) -> dict[str, Any]:
    cfg = cfg or PROVIDER_BIND
    points: list[dict[str, Any]] = []
    first_mode = None
    first_mult = None
    for mult in MULTS:
        summary = simulate(offer_train(n_per_point, mult, cfg.planned_rate), cfg)
        point = {
            "offered_mult": mult,
            "offered_rate": summary["offered_rate"],
            "completed_rate": summary["completed_rate"],
            "n_429": summary["n_429"],
            "n_shed": summary["n_shed"],
            "n_exhausted": summary["n_exhausted"],
            "n_unaccounted": summary["n_unaccounted"],
            "n_collapse": summary["n_collapse"],
            "n_completed": summary["n_completed"],
            "n_offered": summary["n_offered"],
            "max_worker_queue_depth": summary["max_worker_queue_depth"],
            "max_stagger_queue_depth": summary["max_stagger_queue_depth"],
            "scheduler_latency_p50": summary["scheduler_latency_p50"],
            "scheduler_latency_p95": summary["scheduler_latency_p95"],
            "rss_kb": summary["rss_kb"],
            "invariant_ok": summary["invariant_ok"],
            "failure_mode": summary["failure_mode"],
        }
        points.append(point)
        if first_mode is None and summary["failure_mode"]:
            first_mode = summary["failure_mode"]
            first_mult = mult
    healthy_1x = points[0]["failure_mode"] is None and points[0]["n_429"] == 0
    reached_10x = any(p["offered_mult"] >= 10.0 for p in points)
    return {
        "points": points,
        "first_failure_mode": first_mode,
        "first_failure_mult": first_mult,
        "healthy_1x": healthy_1x,
        "reached_10x": reached_10x,
        "n_per_point": n_per_point,
        "planned_rate": cfg.planned_rate,
        "planned_units": cfg.planned_units,
        "mults": list(MULTS),
    }


def program_size_pair(cfg: Config | None = None) -> dict[str, Any]:
    cfg = cfg or PROVIDER_BIND
    one = simulate(offer_train(PLANNED_UNITS, 1.0, cfg.planned_rate), cfg)
    ten = simulate(offer_train(PLANNED_UNITS, 10.0, cfg.planned_rate), cfg)
    return {"n": PLANNED_UNITS, "at_1x": one, "at_10x": ten}


def backpressure_both_states() -> dict[str, Any]:
    n = 24
    live_cfg = WORKER_BIND
    mutant_cfg = Config(
        worker_count=WORKER_BIND.worker_count,
        worker_latency=WORKER_BIND.worker_latency,
        bucket_capacity=WORKER_BIND.bucket_capacity,
        bucket_refill=WORKER_BIND.bucket_refill,
        stagger_window=WORKER_BIND.stagger_window,
        max_worker_queue=WORKER_BIND.max_worker_queue,
        silent_drop=True,
    )
    offers = offer_train(n, 8.0, live_cfg.planned_rate)
    live = simulate(offers, live_cfg)
    mutant = simulate(offers, mutant_cfg)
    return {
        "n": n,
        "live": live,
        "mutant_silent_drop": mutant,
        "live_unaccounted": live["n_unaccounted"],
        "mutant_unaccounted": mutant["n_unaccounted"],
        "live_shed": live["n_shed"],
        "mutant_shed": mutant["n_shed"],
        "discriminator": (
            live["n_unaccounted"] == 0
            and live["n_shed"] > 0
            and mutant["n_unaccounted"] > 0
        ),
    }


def recovery_after_storm(cfg: Config | None = None) -> dict[str, Any]:
    cfg = cfg or PROVIDER_BIND
    baseline = simulate(offer_train(256, 1.0, cfg.planned_rate), cfg)
    storm = offer_train(128, 10.0, cfg.planned_rate, phase=0)
    t1 = storm[-1][0] + 0.5
    calm = [(t1 + i / cfg.planned_rate, 50_000 + i, 1) for i in range(256)]
    mixed = simulate(storm + calm, cfg)
    tail = simulate(calm, cfg)
    base_rate = float(baseline["completed_rate"])
    tail_rate = float(tail["completed_rate"])
    recovered = base_rate > 0 and tail_rate >= 0.8 * base_rate
    return {
        "baseline_1x": baseline,
        "storm_plus_calm": mixed,
        "tail_1x": tail,
        "baseline_completed_rate": base_rate,
        "tail_completed_rate": tail_rate,
        "recovered": recovered,
        "storm_n_429": mixed["n_429"],
    }


def local_stability_control() -> dict[str, Any]:
    simulated = assert_local_stability(10.0, "simulated")
    refused = False
    message = ""
    try:
        assert_local_stability(10.0, "wall")
    except LocalStabilityError as exc:
        refused = True
        message = str(exc)
    return {
        "simulated_10x": simulated,
        "wall_10x_refused": refused,
        "wall_10x_message": message,
        "pass": refused and simulated.get("clock") == "simulated",
    }
