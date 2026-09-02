#!/usr/bin/env python3
"""Per-unit pipelines so one hung unit cannot deadlock its cohort (IMP-0452 / spec 11317).

A phase-wide barrier waits for every sibling before any result is harvested. That is the
cohort-deadlock class: one unit that never returns holds the other 39 in limbo.

This module gives every unit its own pipeline (own timeout, own terminal state) and a
null-tolerant fan-in. Fan-in resolves on the units that have reached a terminal state.
A hung sibling is classified STALLED at its own deadline. A null result is classified
NULL and does not poison the barrier for the rest.

The executor MUST shutdown(wait=False). Joining hung workers at teardown reintroduces
the same cohort deadlock one layer down.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import (
    ALL_COMPLETED,
    FIRST_COMPLETED,
    Future,
    ThreadPoolExecutor,
    wait,
)
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

TERMINAL = frozenset({"SUCCESS", "FAILED", "STALLED", "NULL"})
HANG_RELEASE = threading.Event()


class BarrierPoison(RuntimeError):
    """Raised only by the known-broken fan-in that treats a null slot as cohort failure."""


@dataclass
class UnitSpec:
    unit_id: str
    fn: Callable[[], Any]
    timeout_s: float = 0.4


@dataclass
class UnitResult:
    unit_id: str
    state: str
    value: Any
    started_at: float
    ended_at: float
    elapsed_s: float
    error: str | None = None

    @property
    def terminal(self) -> bool:
        return self.state in TERMINAL


@dataclass
class FanInReport:
    mode: str
    poisoned: bool
    slot_count: int
    success: int
    failed: int
    stalled: int
    nulls: int
    terminal: int
    pending: int
    deadlock: bool
    survivors_complete_s: float
    hung_classified_s: float | None
    cohort_resolved_s: float
    slots: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def hang_forever() -> Any:
    """Deliberately never returns until HANG_RELEASE is set (test cleanup only)."""
    HANG_RELEASE.wait()
    return "unreachable-after-release"


def ok_work(payload: Any) -> Callable[[], Any]:
    def _run() -> Any:
        return payload

    return _run


def null_work() -> Any:
    return None


def _invoke(spec: UnitSpec, started_at: float) -> UnitResult:
    try:
        value = spec.fn()
    except Exception as exc:  # noqa: BLE001 — unit failure is a classified terminal state
        now = time.perf_counter()
        return UnitResult(
            unit_id=spec.unit_id,
            state="FAILED",
            value=None,
            started_at=started_at,
            ended_at=now,
            elapsed_s=now - started_at,
            error=f"{type(exc).__name__}: {exc}",
        )
    now = time.perf_counter()
    if value is None:
        state = "NULL"
    else:
        state = "SUCCESS"
    return UnitResult(
        unit_id=spec.unit_id,
        state=state,
        value=value,
        started_at=started_at,
        ended_at=now,
        elapsed_s=now - started_at,
        error=None,
    )


def _slot(result: UnitResult) -> dict[str, Any]:
    return {
        "unit_id": result.unit_id,
        "state": result.state,
        "value_is_null": result.value is None,
        "elapsed_s": round(result.elapsed_s, 6),
        "error": result.error,
    }


def fan_in(results: Sequence[UnitResult], *, cohort_resolved_s: float) -> FanInReport:
    """Null-tolerant fan-in: a NULL/STALLED/FAILED slot is recorded, never poisons siblings."""
    success = failed = stalled = nulls = 0
    ended_ok: list[float] = []
    hung_at: list[float] = []
    slots: list[dict[str, Any]] = []
    for result in results:
        slots.append(_slot(result))
        if result.state == "SUCCESS":
            success += 1
            ended_ok.append(result.elapsed_s)
        elif result.state == "FAILED":
            failed += 1
            ended_ok.append(result.elapsed_s)
        elif result.state == "NULL":
            nulls += 1
            ended_ok.append(result.elapsed_s)
        elif result.state == "STALLED":
            stalled += 1
            hung_at.append(result.elapsed_s)
    terminal = success + failed + nulls + stalled
    return FanInReport(
        mode="per-unit",
        poisoned=False,
        slot_count=len(results),
        success=success,
        failed=failed,
        stalled=stalled,
        nulls=nulls,
        terminal=terminal,
        pending=0,
        deadlock=False,
        survivors_complete_s=round(max(ended_ok) if ended_ok else 0.0, 6),
        hung_classified_s=round(max(hung_at), 6) if hung_at else None,
        cohort_resolved_s=round(cohort_resolved_s, 6),
        slots=slots,
    )


def poisoning_fan_in(results: Sequence[UnitResult]) -> FanInReport:
    """Known-broken fan-in: a single null poisons the whole barrier (null-poisons-barrier)."""
    values = [r.value for r in results]
    if any(v is None for v in values):
        raise BarrierPoison("null-poisons-barrier: one None result failed the cohort")
    resolved = max((r.elapsed_s for r in results), default=0.0)
    return FanInReport(
        mode="poisoning",
        poisoned=False,
        slot_count=len(results),
        success=len(results),
        failed=0,
        stalled=0,
        nulls=0,
        terminal=len(results),
        pending=0,
        deadlock=False,
        survivors_complete_s=round(resolved, 6),
        hung_classified_s=None,
        cohort_resolved_s=round(resolved, 6),
        slots=[_slot(r) for r in results],
    )


def _stalled(spec: UnitSpec, started_at: float, ended_at: float) -> UnitResult:
    return UnitResult(
        unit_id=spec.unit_id,
        state="STALLED",
        value=None,
        started_at=started_at,
        ended_at=ended_at,
        elapsed_s=ended_at - started_at,
        error="per-unit-timeout",
    )


def run_per_unit(specs: Sequence[UnitSpec]) -> FanInReport:
    """Each unit is its own pipeline. The cohort returns once every unit is terminal,
    including STALLED. Hung workers are not joined."""
    if not specs:
        return fan_in([], cohort_resolved_s=0.0)
    t0 = time.perf_counter()
    started = {spec.unit_id: t0 for spec in specs}
    by_id: dict[str, UnitResult] = {}
    pool = ThreadPoolExecutor(max_workers=len(specs), thread_name_prefix="imp0452")
    try:
        future_of: dict[Future[UnitResult], UnitSpec] = {
            pool.submit(_invoke, spec, t0): spec for spec in specs
        }
        deadline = {fut: t0 + spec.timeout_s for fut, spec in future_of.items()}
        pending: set[Future[UnitResult]] = set(future_of)
        while pending:
            now = time.perf_counter()
            overdue = [
                fut for fut in list(pending) if now >= deadline[fut] and not fut.done()
            ]
            for fut in overdue:
                spec = future_of[fut]
                pending.remove(fut)
                by_id[spec.unit_id] = _stalled(spec, started[spec.unit_id], now)
            if not pending:
                break
            now = time.perf_counter()
            wait_s = min(deadline[fut] - now for fut in pending)
            done, pending = wait(
                pending,
                timeout=max(wait_s, 0.0),
                return_when=FIRST_COMPLETED,
            )
            now = time.perf_counter()
            for fut in done:
                spec = future_of[fut]
                if fut.done() and spec.unit_id not in by_id:
                    by_id[spec.unit_id] = fut.result()
    finally:
        # wait=False is load-bearing: joining a hung worker deadlocks the cohort at teardown.
        pool.shutdown(wait=False, cancel_futures=True)
    ordered = [by_id[spec.unit_id] for spec in specs]
    return fan_in(ordered, cohort_resolved_s=time.perf_counter() - t0)


def run_phase_barrier(
    specs: Sequence[UnitSpec], *, watchdog_s: float
) -> FanInReport:
    """Known-broken phase-wide barrier: wait for ALL, no per-unit timeout.

    Under a watchdog the hung unit leaves the barrier unresolved (deadlock=True),
    and the hung unit is never classified STALLED — it is still pending.
    """
    if not specs:
        return FanInReport(
            mode="phase-barrier",
            poisoned=False,
            slot_count=0,
            success=0,
            failed=0,
            stalled=0,
            nulls=0,
            terminal=0,
            pending=0,
            deadlock=False,
            survivors_complete_s=0.0,
            hung_classified_s=None,
            cohort_resolved_s=0.0,
        )
    t0 = time.perf_counter()
    pool = ThreadPoolExecutor(max_workers=len(specs), thread_name_prefix="imp0452bar")
    try:
        future_of = {pool.submit(_invoke, spec, t0): spec for spec in specs}
        done, not_done = wait(
            set(future_of),
            timeout=watchdog_s,
            return_when=ALL_COMPLETED,
        )
        harvested: list[UnitResult] = []
        for fut in done:
            harvested.append(fut.result())
        pending_ids = [future_of[fut].unit_id for fut in not_done]
        resolved = time.perf_counter() - t0
        success = sum(1 for r in harvested if r.state == "SUCCESS")
        failed = sum(1 for r in harvested if r.state == "FAILED")
        nulls = sum(1 for r in harvested if r.state == "NULL")
        deadlock = bool(not_done)
        ended = [r.elapsed_s for r in harvested]
        return FanInReport(
            mode="phase-barrier",
            poisoned=False,
            slot_count=len(specs),
            success=success,
            failed=failed,
            stalled=0,
            nulls=nulls,
            terminal=success + failed + nulls,
            pending=len(pending_ids),
            deadlock=deadlock,
            survivors_complete_s=round(max(ended) if ended else 0.0, 6),
            hung_classified_s=None,
            cohort_resolved_s=round(resolved, 6),
            slots=[_slot(r) for r in harvested]
            + [
                {
                    "unit_id": uid,
                    "state": "PENDING",
                    "value_is_null": True,
                    "elapsed_s": round(resolved, 6),
                    "error": "phase-barrier-await",
                }
                for uid in pending_ids
            ],
            error="cohort-deadlock" if deadlock else None,
        )
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def report_to_dict(report: FanInReport) -> dict[str, Any]:
    return {
        "mode": report.mode,
        "poisoned": report.poisoned,
        "slot_count": report.slot_count,
        "success": report.success,
        "failed": report.failed,
        "stalled": report.stalled,
        "nulls": report.nulls,
        "terminal": report.terminal,
        "pending": report.pending,
        "deadlock": report.deadlock,
        "survivors_complete_s": report.survivors_complete_s,
        "hung_classified_s": report.hung_classified_s,
        "cohort_resolved_s": report.cohort_resolved_s,
        "error": report.error,
        "terminal_plus_stalled": {
            "terminal_non_stalled": report.success + report.failed + report.nulls,
            "stalled": report.stalled,
        },
    }


def release_hung_workers() -> None:
    """Unstick hang_forever threads after a batch so the process can exit."""
    HANG_RELEASE.set()


def reset_hang_gate() -> None:
    HANG_RELEASE.clear()


def build_hung_batch(
    *,
    batch_size: int = 40,
    hung_index: int = 17,
    timeout_s: float = 0.4,
    prefix: str = "U",
) -> list[UnitSpec]:
    if not 0 <= hung_index < batch_size:
        raise ValueError("hung_index out of range")
    specs: list[UnitSpec] = []
    for i in range(batch_size):
        uid = f"{prefix}-{i:02d}"
        if i == hung_index:
            specs.append(UnitSpec(uid, hang_forever, timeout_s=timeout_s))
        else:
            specs.append(UnitSpec(uid, ok_work({"id": uid, "ok": True}), timeout_s=timeout_s))
    return specs


def build_null_batch(
    *,
    batch_size: int = 40,
    null_index: int = 7,
    timeout_s: float = 0.4,
    prefix: str = "N",
) -> list[UnitSpec]:
    if not 0 <= null_index < batch_size:
        raise ValueError("null_index out of range")
    specs: list[UnitSpec] = []
    for i in range(batch_size):
        uid = f"{prefix}-{i:02d}"
        if i == null_index:
            specs.append(UnitSpec(uid, null_work, timeout_s=timeout_s))
        else:
            specs.append(UnitSpec(uid, ok_work({"id": uid, "ok": True}), timeout_s=timeout_s))
    return specs


def shutdown_source_refuses_join() -> bool:
    """Structural control: the per-unit path must not join hung workers."""
    import inspect

    body = inspect.getsource(run_per_unit)
    return "shutdown(wait=False" in body and "shutdown(wait=True" not in body


def iter_terminal(report: FanInReport) -> Iterable[dict[str, Any]]:
    for slot in report.slots:
        if slot["state"] in TERMINAL:
            yield slot
