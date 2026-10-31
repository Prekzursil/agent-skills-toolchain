"""Confirmation-queue scheduler.

arrival_rate_hz is a required scheduler input and must be > 0.
Claim verdict on an infra event is ignored: classification is typed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .queue import RecordStore, VerdictLaunderingError
from .record import mint_record_id, validate_record
from .taxonomy import FORBIDDEN_INFRA_VERDICTS, map_fault


@dataclass
class Clock:
    now_s: float = 0.0

    def time(self) -> float:
        return float(self.now_s)

    def advance(self, seconds: float) -> None:
        self.now_s = float(self.now_s) + float(seconds)


@dataclass
class Job:
    claim_id: str
    confirmer: dict[str, Any]
    wave: str
    timeout_seconds: int = 30
    job_id: str = ""

    def __post_init__(self) -> None:
        if not self.job_id:
            self.job_id = f"{self.wave}:{self.claim_id}"


@dataclass
class RunnerEvent:
    kind: str
    evidence: str = ""
    claim_verdict: str | None = None
    timeout_seconds: int | None = None
    source_probe: str | None = None
    verifier_probe: str | None = None
    discrepancies: list[str] = field(default_factory=list)


def mark_in_flight(sched: "ConfirmationQueueScheduler", job: Job) -> None:
    sched.in_flight.add(job.job_id)


class ConfirmationQueueScheduler:
    def __init__(
        self,
        arrival_rate_hz: float,
        clock: Clock | None = None,
        vendor_rate_cap_hz: float | None = None,
    ) -> None:
        if arrival_rate_hz is None or float(arrival_rate_hz) <= 0:
            raise ValueError("arrival_rate_hz must be a positive scheduler input")
        self.arrival_rate_hz = float(arrival_rate_hz)
        self.vendor_rate_cap_hz = vendor_rate_cap_hz
        self.clock = clock or Clock(0)
        self.store = RecordStore()
        self.in_flight: set[str] = set()
        self.retries: dict[str, list[str]] = {}
        self.terminal: dict[str, str] = {}
        self._slot = 0
        self.quota_posture = "NOT-CHECKED"

    def stagger_interval_ms(self, vendor: str) -> int:
        del vendor
        hz = float(self.vendor_rate_cap_hz or self.arrival_rate_hz)
        return int(round(1000.0 / hz))

    def _next_slot_ms(self) -> int:
        gap = self.stagger_interval_ms("default")
        slot = self._slot * gap
        self._slot += 1
        return slot

    def _infra_record(self, job: Job, event: RunnerEvent, fault: str, scheduled_at_ms: int) -> dict[str, Any]:
        mapped = map_fault(fault)
        rec = {
            "record_id": mint_record_id(job.job_id, job.claim_id, mapped["fault_class"]),
            "job_id": job.job_id,
            "claim_id": job.claim_id,
            "confirmer": job.confirmer,
            "verdict": "BLOCKED",
            "fault_class": mapped["fault_class"],
            "named_prerequisite": mapped["named_prerequisite"],
            "scheduled_at_ms": scheduled_at_ms,
            "quota_posture": self.quota_posture,
            "discrepancies": list(event.discrepancies or []),
            "residual_caveat": event.evidence,
            "source_probe": None,
            "verifier_probe": None,
            "retries": list(self.retries.get(job.job_id, [])),
            "parked_two_strikes": False,
        }
        if mapped["fault_class"] == "timeout-<n>s":
            rec["timeout_seconds"] = int(event.timeout_seconds or job.timeout_seconds)
        if rec["verdict"] in FORBIDDEN_INFRA_VERDICTS:
            raise VerdictLaunderingError("infra event laundered")
        rec["retries"] = list(self.retries.get(job.job_id, [])) + [event.kind]
        rec["parked_two_strikes"] = len(rec["retries"]) >= 2
        return rec

    def dispatch(self, job: Job, event: RunnerEvent, scheduled_at_ms: int | None = None) -> dict[str, Any]:
        slot = self._next_slot_ms() if scheduled_at_ms is None else int(scheduled_at_ms)
        if job.job_id in self.terminal and self.terminal[job.job_id] == "REFUTED":
            if event.kind == "healthy" and (event.claim_verdict or "").upper() == "CONFIRMED":
                raise VerdictLaunderingError("cannot launder REFUTED to CONFIRMED")
        if event.kind != "healthy":
            if job.job_id in self.in_flight and event.kind in {"healthy", "duplicate"}:
                pass
            fault = {
                "kill": "severed-stream",
                "crash": "severed-stream",
                "http-429": "quota-429-storm",
                "timeout": "timeout-<n>s",
            }.get(event.kind, event.kind)
            rec = self._infra_record(job, event, fault, slot)
            existing = self.store.get(rec["record_id"])
            if existing is not None:
                existing["retries"] = list(existing.get("retries") or []) + [event.kind]
                existing["parked_two_strikes"] = len(existing["retries"]) >= 2
                self.retries[job.job_id] = list(existing["retries"])
                return existing
            self.retries[job.job_id] = list(rec["retries"])
            return self.store.upsert(rec)
        if job.job_id in self.in_flight:
            rec = self._infra_record(job, event, "duplicate-dispatch", slot)
            rec["record_id"] = mint_record_id(job.job_id, job.claim_id, "duplicate-dispatch")
            return self.store.upsert(rec)
        verdict = str(event.claim_verdict or "CONFIRMED").upper()
        rec = {
            "record_id": mint_record_id(job.job_id, job.claim_id, "claim"),
            "job_id": job.job_id,
            "claim_id": job.claim_id,
            "confirmer": job.confirmer,
            "verdict": verdict,
            "fault_class": None,
            "named_prerequisite": None,
            "scheduled_at_ms": slot,
            "quota_posture": self.quota_posture,
            "discrepancies": list(event.discrepancies or []),
            "residual_caveat": event.evidence,
            "source_probe": event.source_probe,
            "verifier_probe": event.verifier_probe,
            "retries": [],
            "parked_two_strikes": False,
        }
        validate_record(rec)
        self.terminal[job.job_id] = verdict
        return self.store.upsert(rec)

    def dispatch_batch(
        self, jobs: list[Job], event_fn: Callable[[Job], RunnerEvent]
    ) -> list[dict[str, Any]]:
        gap = self.stagger_interval_ms("anthropic")
        out = []
        for i, job in enumerate(jobs):
            out.append(self.dispatch(job, event_fn(job), scheduled_at_ms=i * gap))
        return out

    def requeue_blocked(self, job: Job, event: RunnerEvent) -> dict[str, Any]:
        self._slot = max(0, self._slot - 1)
        return self.dispatch(job, event)
