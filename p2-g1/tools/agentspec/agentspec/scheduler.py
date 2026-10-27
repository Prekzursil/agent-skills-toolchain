"""Quota-aware scheduler for IMP-0221."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from agentspec.retry import (
    RATE_LIMITED_BACKOFF_CAP_MS,
    RATE_LIMITED_MAX_RETRIES,
    plan_retry,
)


@dataclass
class UnitRecord:
    unit_id: str
    status: str
    attempts: int = 1
    wait_ms: int = 0


@dataclass
class RunReport:
    submitted: int = 0
    completed: int = 0
    rate_limited: int = 0
    overload: int = 0
    error: int = 0
    lost: int = 0
    accounted: int = 0
    accounting_pct: float = 0.0
    virtual_elapsed_s: float = 0.0
    concurrency_unchanged: bool = True
    max_concurrency_start: int = 0
    max_concurrency_end: int = 0
    terminated: bool = True
    max_attempts_seen: int = 0
    max_wait_ms_seen: int = 0
    records: list[UnitRecord] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "submitted": self.submitted,
            "completed": self.completed,
            "rate_limited": self.rate_limited,
            "overload": self.overload,
            "error": self.error,
            "lost": self.lost,
            "accounted": self.accounted,
            "accounting_pct": self.accounting_pct,
            "virtual_elapsed_s": self.virtual_elapsed_s,
            "concurrency_unchanged": self.concurrency_unchanged,
            "max_concurrency_start": self.max_concurrency_start,
            "max_concurrency_end": self.max_concurrency_end,
            "terminated": self.terminated,
            "max_attempts_seen": self.max_attempts_seen,
            "max_wait_ms_seen": self.max_wait_ms_seen,
        }


class QuotaAwareScheduler:
    def __init__(self, quota: Any, *, max_concurrency: int, clock: Any) -> None:
        self.quota = quota
        self.max_concurrency = int(max_concurrency)
        self.clock = clock

    def run(self, units: Iterable[str], rail: Any) -> RunReport:
        units = list(units)
        report = RunReport(
            submitted=len(units),
            max_concurrency_start=self.max_concurrency,
            max_concurrency_end=self.max_concurrency,
            concurrency_unchanged=True,
        )
        start = int(self.clock.now_ms())
        for uid in units:
            attempt = 1
            last: Any = None
            while True:
                last = rail.admit(uid, attempt=attempt)
                report.max_attempts_seen = max(report.max_attempts_seen, int(last.attempts))
                wait_ms = min(int(last.wait_ms or 0), RATE_LIMITED_BACKOFF_CAP_MS)
                report.max_wait_ms_seen = max(report.max_wait_ms_seen, wait_ms)
                if last.status == "completed":
                    report.completed += 1
                    report.records.append(UnitRecord(uid, "completed", last.attempts, wait_ms))
                    break
                if last.status == "overload":
                    report.overload += 1
                    report.records.append(UnitRecord(uid, "overload", last.attempts, wait_ms))
                    break
                if last.status == "error":
                    report.error += 1
                    report.records.append(UnitRecord(uid, "error", last.attempts, wait_ms))
                    break
                # rate-limited: bounded retry via plan_retry
                decision = plan_retry("rate-limited", attempt=attempt)
                if not decision.retry or attempt > RATE_LIMITED_MAX_RETRIES:
                    report.rate_limited += 1
                    report.records.append(UnitRecord(uid, "rate-limited", last.attempts, wait_ms))
                    break
                cap_wait = min(wait_ms or decision.backoff_ms, RATE_LIMITED_BACKOFF_CAP_MS)
                if cap_wait:
                    self.clock.advance(int(cap_wait))
                attempt += 1
        end = int(self.clock.now_ms())
        report.virtual_elapsed_s = max(0.0, (end - start) / 1000.0)
        report.accounted = (
            report.completed + report.rate_limited + report.overload + report.error
        )
        report.lost = 0
        report.accounting_pct = 100.0 if report.submitted and report.accounted == report.submitted else (
            100.0 * report.accounted / report.submitted if report.submitted else 0.0
        )
        report.terminated = True
        return report


def run_naive_drop(units: Iterable[str], rail: Any) -> RunReport:
    units = list(units)
    report = RunReport(submitted=len(units), concurrency_unchanged=True)
    for uid in units:
        result = rail.admit(uid, attempt=1)
        if result.status == "completed":
            report.completed += 1
            report.records.append(UnitRecord(uid, "completed", 1, 0))
        else:
            report.lost += 1
            report.records.append(UnitRecord(uid, "lost", 1, int(result.wait_ms or 0)))
    report.accounted = report.completed + report.lost
    report.accounting_pct = (
        100.0 * report.accounted / report.submitted if report.submitted else 0.0
    )
    report.terminated = True
    return report


def unbounded_429_loop(rail: Any, tripwire: int = 80) -> dict[str, Any]:
    n = 0
    hit = False
    while n < tripwire:
        n += 1
        result = rail.admit(f"u{n}", attempt=n)
        if result.status != "rate-limited":
            break
        if n >= tripwire:
            hit = True
            break
    else:
        hit = True
    return {"hit_tripwire": hit, "iterations": n, "tripwire": tripwire}
