"""Arrival-stagger scheduler: per-provider token bucket + serial inflight.

Logical count (tokens over time) is enforced separately from simultaneous
concurrency (max_inflight). Callers cannot stampede a provider: burst_capacity
defaults to 1 and inflight is 1, so a herd serialises into jittered arrivals.
"""
from __future__ import annotations

import json
import random
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator


class Clock:
    def now(self) -> float:
        raise NotImplementedError

    def sleep(self, seconds: float) -> None:
        raise NotImplementedError


class WallClock(Clock):
    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


class VirtualClock(Clock):
    """Deterministic clock: sleep advances t without wall wait."""

    def __init__(self, start: float = 0.0) -> None:
        self._t = float(start)
        self._lock = threading.Lock()

    def now(self) -> float:
        with self._lock:
            return self._t

    def sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        with self._lock:
            self._t += float(seconds)


@dataclass
class Admission:
    provider: str
    admitted_at: float
    waited_seconds: float
    tokens_after: float
    inflight_after: int
    logical_count: int
    _release: Callable[[], None]
    _released: bool = False

    def release(self) -> None:
        if not self._released:
            self._release()
            self._released = True

    def __enter__(self) -> "Admission":
        return self

    def __exit__(self, *exc: object) -> bool:
        self.release()
        return False


class ProviderGate:
    """One provider: token bucket (logical rate) + inflight cap (concurrency)."""

    def __init__(
        self,
        name: str,
        spec: dict[str, Any],
        clock: Clock,
        rng: random.Random,
    ) -> None:
        self.name = name
        tpm = float(spec["tokens_per_minute"])
        if tpm <= 0:
            raise ValueError(f"{name}: tokens_per_minute must be positive")
        self.tokens_per_minute = tpm
        self.burst_capacity = float(spec.get("burst_capacity", 1) or 1)
        if self.burst_capacity < 1:
            raise ValueError(f"{name}: burst_capacity must be >= 1")
        self.jitter_seconds = float(spec.get("jitter_seconds", 0) or 0)
        self.max_inflight = int(spec.get("max_inflight", 1) or 1)
        if self.max_inflight < 1:
            raise ValueError(f"{name}: max_inflight must be >= 1")
        self.clock = clock
        self.rng = rng
        self.lock = threading.Lock()
        self.tokens = float(self.burst_capacity)
        self.last_refill = clock.now()
        self.inflight = 0
        self.logical_count = 0
        self.arrivals: list[float] = []

    def refill_per_second(self) -> float:
        return self.tokens_per_minute / 60.0

    def _refill_unlocked(self) -> None:
        now = self.clock.now()
        elapsed = max(0.0, now - self.last_refill)
        self.tokens = min(
            self.burst_capacity,
            self.tokens + elapsed * self.refill_per_second(),
        )
        self.last_refill = now

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            self._refill_unlocked()
            return {
                "provider": self.name,
                "tokens_per_minute": self.tokens_per_minute,
                "burst_capacity": self.burst_capacity,
                "max_inflight": self.max_inflight,
                "tokens": self.tokens,
                "inflight": self.inflight,
                "logical_count": self.logical_count,
                "concurrency_available": self.inflight < self.max_inflight,
                "tokens_available": self.tokens >= 1.0,
            }

    def _release_unlocked(self) -> None:
        if self.inflight <= 0:
            raise RuntimeError(f"{self.name}: inflight underflow")
        self.inflight -= 1

    def admit(self) -> Admission:
        """Take one token. Sleeps never hold the gate lock (release must proceed)."""
        waited = 0.0
        while True:
            pause = 0.0
            taken = False
            jitter = 0.0
            tokens_after = 0.0
            inflight_after = 0
            logical = 0
            with self.lock:
                if self.inflight >= self.max_inflight:
                    pause = 0.001
                else:
                    self._refill_unlocked()
                    if self.tokens >= 1.0:
                        self.tokens -= 1.0
                        if self.tokens < -1e-9:
                            raise RuntimeError(f"{self.name}: token bucket went negative")
                        if self.tokens < 0:
                            self.tokens = 0.0
                        self.inflight += 1
                        if self.jitter_seconds > 0:
                            jitter = self.rng.uniform(0.0, self.jitter_seconds)
                        tokens_after = self.tokens
                        inflight_after = self.inflight
                        self.logical_count += 1
                        logical = self.logical_count
                        taken = True
                    else:
                        need = 1.0 - self.tokens
                        pause = need / self.refill_per_second()
            if taken:
                if jitter > 0:
                    self.clock.sleep(jitter)
                    waited += jitter
                at = self.clock.now()
                with self.lock:
                    self.arrivals.append(at)

                def _release() -> None:
                    with self.lock:
                        self._release_unlocked()

                return Admission(
                    provider=self.name,
                    admitted_at=at,
                    waited_seconds=waited,
                    tokens_after=tokens_after,
                    inflight_after=inflight_after,
                    logical_count=logical,
                    _release=_release,
                )
            if pause <= 0:
                pause = 0.001
            self.clock.sleep(pause)
            waited += pause


def max_in_window(arrivals: list[float], window: float = 60.0) -> int:
    """Max arrivals in any half-open [t, t+window)."""
    if not arrivals:
        return 0
    times = sorted(arrivals)
    best = 0
    for i, t0 in enumerate(times):
        n = 0
        for t1 in times[i:]:
            if t1 - t0 < window:
                n += 1
            else:
                break
        if n > best:
            best = n
    return best


def load_config(path: Path) -> dict[str, dict[str, Any]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    providers = doc.get("providers")
    if not isinstance(providers, dict) or not providers:
        raise ValueError("providers.json missing providers")
    return {str(k): dict(v) for k, v in providers.items()}


class DurableQueue:
    """JSON queue: a killed scheduler must not lose queued or inflight work."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.jobs: list[dict[str, Any]] = []
        if path.is_file() and path.stat().st_size > 0:
            doc = json.loads(path.read_text(encoding="utf-8"))
            self.jobs = list(doc.get("jobs") or [])
            for job in self.jobs:
                if job.get("status") == "inflight":
                    job["status"] = "queued"
                    job["recovered_from_inflight"] = True

    def enqueue(self, job_id: str, provider: str, payload: Any) -> None:
        self.jobs.append(
            {
                "id": job_id,
                "provider": provider,
                "payload": payload,
                "status": "queued",
                "attempts": 0,
            }
        )
        self.checkpoint()

    def pending(self) -> list[dict[str, Any]]:
        return [j for j in self.jobs if j.get("status") in {"queued", "inflight"}]

    def mark(self, job_id: str, status: str) -> None:
        for job in self.jobs:
            if job.get("id") == job_id:
                job["status"] = status
                if status == "inflight":
                    job["attempts"] = int(job.get("attempts") or 0) + 1
                break
        self.checkpoint()

    def checkpoint(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        payload = {"jobs": self.jobs}
        tmp.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        tmp.replace(self.path)

    def ids(self, status: str | None = None) -> list[str]:
        if status is None:
            return [str(j["id"]) for j in self.jobs]
        return [str(j["id"]) for j in self.jobs if j.get("status") == status]


class Scheduler:
    def __init__(
        self,
        config: dict[str, dict[str, Any]],
        clock: Clock | None = None,
        rng: random.Random | None = None,
        queue_path: Path | None = None,
    ) -> None:
        self.clock = clock or VirtualClock()
        self.rng = rng or random.Random(29)
        self.gates = {
            name: ProviderGate(name, spec, self.clock, self.rng)
            for name, spec in config.items()
        }
        self.queue = DurableQueue(queue_path) if queue_path is not None else None

    def gate(self, provider: str) -> ProviderGate:
        if provider not in self.gates:
            raise KeyError(f"unknown provider {provider!r}")
        return self.gates[provider]

    def admit(self, provider: str) -> Admission:
        return self.gate(provider).admit()

    def arrival_histogram(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for name, g in self.gates.items():
            mx = max_in_window(g.arrivals)
            out[name] = {
                "arrivals": list(g.arrivals),
                "n": len(g.arrivals),
                "tokens_per_minute": g.tokens_per_minute,
                "max_in_window_s60": mx,
                "within_configured_rate": mx <= g.tokens_per_minute,
            }
        return out

    def drain(
        self,
        transport: Callable[[dict[str, Any]], dict[str, Any]],
        stop_after: int | None = None,
        crash_before_complete_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run queued work through admit+transport. Persist before/after each job."""
        if self.queue is None:
            raise RuntimeError("drain requires queue_path")
        results: list[dict[str, Any]] = []
        done_n = 0
        while True:
            pending = self.queue.pending()
            if not pending:
                break
            job = pending[0]
            jid = str(job["id"])
            self.queue.mark(jid, "inflight")
            if crash_before_complete_id is not None and jid == crash_before_complete_id:
                return results
            with self.admit(str(job["provider"])) as adm:
                resp = transport(job)
            self.queue.mark(jid, "done")
            results.append(
                {
                    "id": jid,
                    "status": resp.get("status"),
                    "admitted_at": adm.admitted_at,
                    "waited_seconds": adm.waited_seconds,
                }
            )
            done_n += 1
            if stop_after is not None and done_n >= stop_after:
                break
        return results


def iter_jobs(n: int, provider: str, prefix: str = "job") -> Iterator[dict[str, Any]]:
    for i in range(n):
        yield {"id": f"{prefix}-{i:04d}", "provider": provider, "payload": {"i": i}}
