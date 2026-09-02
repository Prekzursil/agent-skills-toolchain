"""429/529-aware work dispatcher under a mock HTTP limiter.

Correct policy:
  * honour Retry-After on 429 (delta-seconds)
  * retry the same in-flight unit; do not spawn a second worker
  * 529/overload uses fallback backoff and MUST NOT reduce concurrency
  * unit work runs once, on the first 200, then the unit is complete

Mutants exist so both-states controls can fail on purpose.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field

from clock import VirtualClock
from mock_limiter import MockLimiter, Response


def parse_retry_after(headers: dict[str, str], fallback: float) -> float:
    raw = headers.get("Retry-After")
    if raw is None:
        raw = headers.get("retry-after")
    if raw is None or str(raw).strip() == "":
        return float(fallback)
    try:
        return max(0.0, float(raw))
    except ValueError:
        return float(fallback)


@dataclass
class Worker:
    worker_id: str
    unit_id: str
    wake_at: float
    attempts: int = 0
    work_done: bool = False


@dataclass
class RunResult:
    completed: list[str]
    work_runs: dict[str, int]
    concurrency_initial: int
    concurrency_final: int
    events: list[dict[str, object]]
    now: float
    failed: list[str] = field(default_factory=list)


class Dispatcher:
    def __init__(
        self,
        client: MockLimiter,
        clock: VirtualClock,
        *,
        concurrency: int = 4,
        honor_retry_after: bool = True,
        self_throttle_on_overload: bool = False,
        allow_duplicate_retry_workers: bool = False,
        fallback_backoff: float = 1.0,
        max_attempts: int = 8,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        self.client = client
        self.clock = clock
        self.configured_concurrency = int(concurrency)
        self.concurrency = int(concurrency)
        self.honor_retry_after = honor_retry_after
        self.self_throttle_on_overload = self_throttle_on_overload
        self.allow_duplicate_retry_workers = allow_duplicate_retry_workers
        self.fallback_backoff = float(fallback_backoff)
        self.max_attempts = int(max_attempts)
        self.work_runs: Counter[str] = Counter()

    def _active_for(self, in_flight: dict[str, Worker], unit_id: str) -> list[Worker]:
        return [w for w in in_flight.values() if w.unit_id == unit_id]

    def run(self, unit_ids: list[str]) -> RunResult:
        pending: deque[str] = deque(unit_ids)
        in_flight: dict[str, Worker] = {}
        completed: dict[str, str] = {}
        failed: list[str] = []
        seq = 0
        safety = 0
        while pending or in_flight:
            safety += 1
            if safety > 100000:
                raise RuntimeError("dispatcher runaway")
            while len(in_flight) < self.concurrency and pending:
                uid = pending.popleft()
                if uid in completed or uid in failed:
                    continue
                active = self._active_for(in_flight, uid)
                if active and not self.allow_duplicate_retry_workers:
                    continue
                if self.allow_duplicate_retry_workers and len(active) >= 2:
                    continue
                seq += 1
                wid = uid if uid not in in_flight else f"{uid}::w{seq}"
                in_flight[wid] = Worker(wid, uid, wake_at=self.clock.now)
            if not in_flight:
                break
            wid = min(in_flight, key=lambda k: in_flight[k].wake_at)
            worker = in_flight[wid]
            delay = worker.wake_at - self.clock.now
            if delay > 0:
                self.clock.sleep(delay)
            resp: Response = self.client.request(worker.unit_id, worker.worker_id)
            worker.attempts += 1
            if resp.status == 200:
                if not worker.work_done:
                    self.work_runs[worker.unit_id] += 1
                    worker.work_done = True
                completed[worker.unit_id] = worker.worker_id
                del in_flight[wid]
                continue
            if resp.status == 429:
                ra = parse_retry_after(resp.headers, self.fallback_backoff)
                wait = ra if self.honor_retry_after else 0.0
                worker.wake_at = self.clock.now + wait
                if self.allow_duplicate_retry_workers:
                    extras = self._active_for(in_flight, worker.unit_id)
                    if len(extras) < 2:
                        pending.appendleft(worker.unit_id)
                if worker.attempts >= self.max_attempts:
                    failed.append(worker.unit_id)
                    del in_flight[wid]
                continue
            if resp.status in {529, 503, 500}:
                if self.self_throttle_on_overload:
                    self.concurrency = max(1, self.concurrency - 1)
                worker.wake_at = self.clock.now + self.fallback_backoff
                if worker.attempts >= self.max_attempts:
                    failed.append(worker.unit_id)
                    del in_flight[wid]
                continue
            failed.append(worker.unit_id)
            del in_flight[wid]
        return RunResult(
            completed=sorted(completed),
            work_runs=dict(self.work_runs),
            concurrency_initial=self.configured_concurrency,
            concurrency_final=self.concurrency,
            events=self.client.timeline(),
            now=self.clock.now,
            failed=failed,
        )
