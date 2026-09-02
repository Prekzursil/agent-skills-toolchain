"""Simulated commit-accounting kernel.

Process creation fails when a spawn would push commit_charge past commit_limit.
Working set (RSS analog) stays far below RAM: committed-but-untouched pages.
This is the Event 2004 class without driving the host toward freeze.
"""
from __future__ import annotations

from commit import Sample

PROCESS_CREATION_FAIL = "process-creation-failed"
RESCUE_COMMIT = 4096
RESCUE_RSS = 4096


class LogicalClock:
    def __init__(self) -> None:
        self.ns = 0

    def tick(self, delta_ns: int = 1_000_000) -> int:
        self.ns += delta_ns
        return self.ns


class SimulatedCommitKernel:
    def __init__(
        self,
        *,
        commit_limit: int,
        ram_total: int,
        commit_per_proc: int,
        rss_per_proc: int,
        clock: LogicalClock | None = None,
    ) -> None:
        self.commit_limit = commit_limit
        self.ram_total = ram_total
        self.commit_per_proc = commit_per_proc
        self.rss_per_proc = rss_per_proc
        self.clock = clock or LogicalClock()
        self.commit_charge = 0
        self.working_set = 0
        self.n_processes = 0
        self.history: list[Sample] = []

    def peek(self, step: int = 0) -> Sample:
        return Sample(
            step=step,
            ts_ns=self.clock.ns,
            commit_charge=self.commit_charge,
            available_commit=self.commit_limit - self.commit_charge,
            commit_limit=self.commit_limit,
            working_set=self.working_set,
            ram_total=self.ram_total,
            n_processes=self.n_processes,
            event="peek",
        )

    def snapshot(self, step: int, event: str) -> Sample:
        s = Sample(
            step=step,
            ts_ns=self.clock.ns,
            commit_charge=self.commit_charge,
            available_commit=self.commit_limit - self.commit_charge,
            commit_limit=self.commit_limit,
            working_set=self.working_set,
            ram_total=self.ram_total,
            n_processes=self.n_processes,
            event=event,
        )
        self.history.append(s)
        return s

    def try_spawn(
        self,
        step: int,
        *,
        commit: int | None = None,
        rss: int | None = None,
        event_ok: str = "spawn-ok",
    ) -> tuple[bool, Sample]:
        c = self.commit_per_proc if commit is None else commit
        r = self.rss_per_proc if rss is None else rss
        self.clock.tick()
        if self.commit_charge + c > self.commit_limit:
            return False, self.snapshot(step, PROCESS_CREATION_FAIL)
        self.commit_charge += c
        self.working_set += r
        self.n_processes += 1
        return True, self.snapshot(step, event_ok)
