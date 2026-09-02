#!/usr/bin/env python3
"""Windowed token-bucket accounting used by the B07 dispatcher/scheduler.

Two surfaces:
  * TokenBucket.take() — lock-protected CAS loop for live threads.
  * SimBucket.step()   — one LOAD or CAS micro-step for a deterministic
    interleaving machine. The mutant path drops the CAS compare so a stale
    snapshot still stores.

Internal invariant (signal a): after every successful mutation,
0 <= tokens <= capacity.

Permit log (signal b): every granted take appends {taker_id, amount,
window_id, seq}. An external auditor that never reads tokens can recompute
per-window totals from this log alone.
"""
from __future__ import annotations

import threading
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any


class InvariantError(AssertionError):
    """Token-bucket internal invariant failed."""


@dataclass
class Permit:
    taker_id: int
    amount: int
    window_id: int
    seq: int
    granted: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "taker_id": self.taker_id,
            "amount": self.amount,
            "window_id": self.window_id,
            "seq": self.seq,
            "granted": self.granted,
        }


class TokenBucket:
    """Capacity-C windowed bucket. take() never publishes a negative balance."""

    def __init__(self, capacity: int, *, atomic: bool = True) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._tokens = capacity
        self._atomic = atomic
        self._lock = threading.Lock()
        self.window_id = 0
        self.permits: list[Permit] = []
        self._seq = 0
        self.invariant_trips: list[str] = []

    def _guard(self) -> threading.Lock | nullcontext[None]:
        return self._lock if self._atomic else nullcontext()

    def tokens(self) -> int:
        with self._guard():
            return self._tokens

    def _invariant(self) -> None:
        t = self._tokens
        if t < 0:
            msg = f"negative tokens={t} capacity={self.capacity} window={self.window_id}"
            self.invariant_trips.append(msg)
            raise InvariantError(msg)
        if t > self.capacity:
            msg = f"overfull tokens={t} capacity={self.capacity} window={self.window_id}"
            self.invariant_trips.append(msg)
            raise InvariantError(msg)

    def _grant(self, taker_id: int, n: int) -> None:
        self._seq += 1
        self.permits.append(
            Permit(
                taker_id=taker_id,
                amount=n,
                window_id=self.window_id,
                seq=self._seq,
                granted=True,
            )
        )

    def take(self, n: int = 1, taker_id: int = 0) -> bool:
        if n < 1:
            raise ValueError("n must be >= 1")
        while True:
            with self._guard():
                snap = self._tokens
                if snap < n:
                    return False
                if self._atomic and self._tokens != snap:
                    continue
                self._tokens = self._tokens - n
                self._invariant()
                self._grant(taker_id, n)
                return True

    def refill(self) -> int:
        with self._guard():
            self.window_id += 1
            self._tokens = self.capacity
            self._invariant()
            return self.window_id

    def permit_dicts(self) -> list[dict[str, Any]]:
        return [p.as_dict() for p in self.permits]


@dataclass
class Actor:
    aid: int
    amount: int = 1
    pc: int = 0  # 0=LOAD, 1=CAS, 2=done
    snap: int | None = None
    granted: bool | None = None
    retries: int = 0


@dataclass
class SimBucket:
    """Step-level token bucket for randomized interleavings."""

    capacity: int
    mutant: bool = False
    tokens: int = field(init=False)
    window_id: int = 0
    permits: list[Permit] = field(default_factory=list)
    seq: int = 0
    invariant_trips: list[str] = field(default_factory=list)
    saw_negative: bool = False
    min_tokens: int = field(init=False)

    def __post_init__(self) -> None:
        if self.capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.tokens = self.capacity
        self.min_tokens = self.capacity

    def _note_tokens(self) -> None:
        if self.tokens < self.min_tokens:
            self.min_tokens = self.tokens
        if self.tokens < 0:
            self.saw_negative = True
            self.invariant_trips.append(
                f"negative tokens={self.tokens} window={self.window_id}"
            )

    def refill(self) -> None:
        self.window_id += 1
        self.tokens = self.capacity
        self._note_tokens()

    def cas(self, expected: int, new: int) -> bool:
        if self.mutant:
            # Mutation: drop the compare. Stale snapshots still store.
            self.tokens = self.tokens - (expected - new)
            self._note_tokens()
            return True
        if self.tokens == expected:
            self.tokens = new
            self._note_tokens()
            return True
        return False

    def _grant(self, actor: Actor) -> None:
        self.seq += 1
        self.permits.append(
            Permit(
                taker_id=actor.aid,
                amount=actor.amount,
                window_id=self.window_id,
                seq=self.seq,
                granted=True,
            )
        )

    def step(self, actor: Actor) -> str:
        """Advance one micro-step. Returns the op name."""
        if actor.pc == 2:
            return "idle"
        if actor.pc == 0:
            actor.snap = self.tokens
            actor.pc = 1
            return "load"
        assert actor.snap is not None
        snap = actor.snap
        if snap < actor.amount:
            actor.granted = False
            actor.pc = 2
            return "deny"
        if self.cas(snap, snap - actor.amount):
            self._grant(actor)
            actor.granted = True
            actor.pc = 2
            return "grant"
        actor.retries += 1
        actor.snap = None
        actor.pc = 0
        return "retry"

    def permit_dicts(self) -> list[dict[str, Any]]:
        return [p.as_dict() for p in self.permits]


def audit_permits(permits: list[dict[str, Any]], capacity: int) -> dict[str, Any]:
    """Independent of SimBucket.tokens / TokenBucket._tokens.

    Recomputes issued-permit totals per window from the log only.
    """
    per_window: dict[int, int] = {}
    for p in permits:
        if not p.get("granted", True):
            continue
        w = int(p["window_id"])
        per_window[w] = per_window.get(w, 0) + int(p["amount"])
    over = {str(w): n for w, n in per_window.items() if n > capacity}
    return {
        "ok": not over,
        "capacity": capacity,
        "per_window": {str(w): n for w, n in sorted(per_window.items())},
        "over_capacity_windows": over,
        "total_granted": sum(per_window.values()),
        "windows": len(per_window),
    }


def check_run(bucket: SimBucket, actors: list[Actor]) -> dict[str, Any]:
    log = bucket.permit_dicts()
    external = audit_permits(log, bucket.capacity)
    granted = sum(1 for a in actors if a.granted is True)
    denied = sum(1 for a in actors if a.granted is False)
    unfinished = sum(1 for a in actors if a.granted is None)
    violations: list[str] = []
    if bucket.saw_negative or bucket.tokens < 0:
        violations.append(f"negative_tokens:{bucket.tokens}")
    if bucket.tokens > bucket.capacity:
        violations.append(f"overfull:{bucket.tokens}>{bucket.capacity}")
    if bucket.invariant_trips:
        violations.append("internal_invariant:" + bucket.invariant_trips[0])
    if not external["ok"]:
        violations.append(f"external_audit_over_issue:{external['over_capacity_windows']}")
    # Accounting: grants this window cannot exceed capacity, and live tokens
    # plus grants in the current window cannot exceed capacity (no refill
    # leftover from a prior window is held as tokens after refill()).
    current_granted = sum(
        p.amount for p in bucket.permits if p.window_id == bucket.window_id
    )
    if current_granted + (bucket.tokens if bucket.tokens > 0 else 0) > bucket.capacity:
        # After a mutant over-issue, tokens may be negative; treat that as
        # already recorded. This identity catches over-issue with tokens==0.
        if bucket.tokens >= 0:
            violations.append(
                f"window_identity:{current_granted}+{bucket.tokens}>{bucket.capacity}"
            )
    return {
        "ok": not violations,
        "violations": violations,
        "granted": granted,
        "denied": denied,
        "tokens": bucket.tokens,
        "min_tokens": bucket.min_tokens,
        "internal_invariant_trips": list(bucket.invariant_trips),
        "external_audit": external,
        "capacity": bucket.capacity,
        "window_id": bucket.window_id,
        "mutant": bucket.mutant,
        "permit_count": len(log),
        "unfinished": unfinished,
    }


def execute_schedule(
    schedule: list[tuple[str, int]],
    *,
    n_takers: int,
    capacity: int,
    mutant: bool,
) -> tuple[SimBucket, list[Actor], dict[str, Any]]:
    bucket = SimBucket(capacity=capacity, mutant=mutant)
    actors = [Actor(i) for i in range(n_takers)]
    for kind, idx in schedule:
        if kind == "refill":
            bucket.refill()
            continue
        actor = actors[idx]
        if actor.pc != 2:
            bucket.step(actor)
    # Do not drain leftover actors: a shrinked prefix must replay exactly.
    result = check_run(bucket, actors)
    return bucket, actors, result
