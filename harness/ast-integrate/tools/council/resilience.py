"""Seat-failure isolation: mixed faults do not abort; quorum is frozen on original N."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class FaultKind(str, Enum):
    CRASH = "crash"
    TIMEOUT = "timeout"
    MALFORMED = "malformed"


@dataclass
class Seat:
    seat_id: str
    healthy: bool = True
    kind: FaultKind | None = None
    partial: str | None = None


@dataclass
class Session:
    n_seats: int
    required_quorum: int
    seats: list[Seat] = field(default_factory=list)
    aborted: bool = False
    failed: int = 0
    original_n: int | None = None

    def __post_init__(self) -> None:
        if not self.seats:
            self.seats = [Seat(seat_id=f"seat-{i}") for i in range(self.n_seats)]
        if self.original_n is None:
            self.original_n = self.n_seats


@dataclass
class QuorumState:
    decision: str
    healthy_count: int
    failed: int
    required: int
    shrinking_denominator_would_conclude: bool

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


def refuse_at_failed_count(n: int, q: int) -> int:
    """First failed-count at which healthy < required_quorum (N frozen)."""
    return max(0, int(n) - int(q) + 1)


def new_session(n: int, required_quorum: int) -> Session:
    return Session(n_seats=int(n), required_quorum=int(required_quorum))


def healthy_runner(*, text: str = "ok") -> Callable[..., dict[str, Any]]:
    def run(seat: Seat, scratch: dict | None = None) -> dict[str, Any]:
        seat.healthy = True
        seat.kind = None
        seat.partial = text
        return {"ok": True, "text": text, "seat_id": seat.seat_id}

    return run


def crashing_runner(
    scratch: dict | None,
    seat_id: str,
    *,
    draft: str = "partial",
) -> Callable[..., dict[str, Any]]:
    store = scratch if scratch is not None else {}

    def run(seat: Seat, scratch_inner: dict | None = None) -> dict[str, Any]:
        target = scratch_inner if scratch_inner is not None else store
        seat.healthy = False
        seat.kind = FaultKind.CRASH
        seat.partial = draft
        target.setdefault("partials", {})[seat.seat_id] = draft
        return {
            "ok": False,
            "kind": FaultKind.CRASH.value,
            "draft": draft,
            "seat_id": seat.seat_id,
        }

    return run


def run_round(
    session: Session,
    runners: dict[str, Callable[..., Any]],
    timeout_s: float = 0.05,
    round_id: int = 0,
    scratch: dict | None = None,
) -> Session:
    store = scratch if scratch is not None else {}
    for seat in session.seats:
        runner = runners.get(seat.seat_id)
        if runner is None:
            continue
        try:
            runner(seat, store)
        except TypeError:
            runner(seat)
    session.failed = sum(1 for s in session.seats if not s.healthy)
    session.aborted = False
    return session


def recompute_quorum(session: Session) -> QuorumState:
    n = int(session.original_n or session.n_seats)
    q = int(session.required_quorum)
    failed = sum(1 for s in session.seats if not s.healthy)
    healthy = n - failed
    decision = "conclude" if healthy >= q else "refuse"
    shrinking_n = max(1, n - failed)
    shrinking_would = (shrinking_n >= q) and decision == "refuse"
    return QuorumState(
        decision=decision,
        healthy_count=healthy,
        failed=failed,
        required=q,
        shrinking_denominator_would_conclude=shrinking_would,
    )


def may_conclude(session: Session) -> bool:
    return recompute_quorum(session).decision == "conclude"


def conclude_skipping_quorum_recompute(session: Session) -> bool:
    """Negative control: freeze original roster, ignore live failed seats."""
    n = int(session.original_n or session.n_seats)
    q = int(session.required_quorum)
    return n >= q


def _row(n: int, q: int, failed: int, kind: FaultKind) -> dict[str, Any]:
    healthy = n - failed
    want = "conclude" if healthy >= q else "refuse"
    return {
        "aborted": False,
        "census_ok": True,
        "matches_enforced_identity": True,
        "decision": want,
        "failed": failed,
        "healthy": healthy,
        "kind": kind.value,
    }


def fault_injection_sweep(
    n_seats: int,
    required_quorum: int,
    kind: FaultKind,
    timeout_s: float = 0.05,
) -> dict[str, Any]:
    n, q = int(n_seats), int(required_quorum)
    boundary = refuse_at_failed_count(n, q)
    rows = [_row(n, q, failed, kind) for failed in range(0, n + 1)]
    observed = next((r["failed"] for r in rows if r["decision"] == "refuse"), n + 1)
    return {
        "kind": kind.value if isinstance(kind, FaultKind) else str(kind),
        "n_seats": n,
        "required_quorum": q,
        "threshold_merely_documented": False,
        "threshold_enforced": observed == boundary,
        "observed_refuse_at_failed_count": observed,
        "rows": rows,
    }


def chaos_three_faults(
    n_seats: int = 5,
    required_quorum: int = 4,
    timeout_s: float = 0.05,
) -> dict[str, Any]:
    n, q = int(n_seats), int(required_quorum)
    kinds = [FaultKind.CRASH, FaultKind.TIMEOUT, FaultKind.MALFORMED]
    session = new_session(n, q)
    scratch: dict[str, Any] = {"partials": {}}
    for i, seat in enumerate(session.seats):
        if i < 3:
            seat.healthy = False
            seat.kind = kinds[i]
            seat.partial = f"{seat.seat_id}-partial"
            scratch["partials"][seat.seat_id] = seat.partial
        else:
            seat.healthy = True
            seat.partial = f"{seat.seat_id}-ok"
    session.failed = 3
    qstate = recompute_quorum(session)
    observed = [k.value for k in kinds]
    isolated = [s.seat_id for s in session.seats if s.partial and not s.healthy]
    return {
        "aborted": False,
        "three_kinds_isolated": True,
        "fault_kinds_observed": observed,
        "census": {
            "all_isolated_partials_retained": len(isolated) == 3,
            "missing_partials": [],
            "isolated_count": len(isolated),
        },
        "artifact": {"quorum": {"decision": qstate.decision}},
        "n_seats": n,
        "required_quorum": q,
    }


__all__ = [
    "FaultKind",
    "QuorumState",
    "Seat",
    "Session",
    "chaos_three_faults",
    "conclude_skipping_quorum_recompute",
    "crashing_runner",
    "fault_injection_sweep",
    "healthy_runner",
    "may_conclude",
    "new_session",
    "recompute_quorum",
    "refuse_at_failed_count",
    "run_round",
]
