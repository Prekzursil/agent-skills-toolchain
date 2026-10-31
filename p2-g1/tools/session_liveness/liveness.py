"""Two-signal session liveness: CPU delta AND artifact byte-growth."""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Iterable

EVIDENCE_WINDOW_SECONDS = 2.0
VERDICT_ALIVE = "ALIVE"
VERDICT_NOT_ALIVE = "NOT-ALIVE"
VERDICT_UNDECIDABLE = "UNDECIDABLE"
VERDICTS = (VERDICT_ALIVE, VERDICT_NOT_ALIVE, VERDICT_UNDECIDABLE)


@dataclass
class Observation:
    name: str
    pid: int
    running: bool
    cpu: float
    bytes: int
    t: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "pid": self.pid,
            "running": self.running,
            "cpu": self.cpu,
            "bytes": self.bytes,
            "t": self.t,
        }


@dataclass
class Verdict:
    verdict: str
    cpu_delta: float
    byte_growth: int
    signals_used: tuple[str, str] = ("process-cpu-delta", "artifact-byte-growth")
    running: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "cpu_delta": self.cpu_delta,
            "byte_growth": self.byte_growth,
            "signals_used": list(self.signals_used),
            "running": self.running,
        }


def observation_field_names() -> list[str]:
    return [f.name for f in fields(Observation)]


def api_rejects_mtime(kwargs: dict[str, Any]) -> bool:
    banned = {k for k in kwargs if "mtime" in str(k).lower()}
    return bool(banned)


def observe(handle) -> Observation:
    return handle.observe()


def classify(t0: Observation, t1: Observation, *, window_seconds: float = EVIDENCE_WINDOW_SECONDS) -> Verdict:
    cpu_delta = float(t1.cpu) - float(t0.cpu)
    byte_growth = int(t1.bytes) - int(t0.bytes)
    running = bool(t1.running)
    both = cpu_delta > 0 and byte_growth > 0
    none = cpu_delta <= 0 and byte_growth <= 0
    if both and running:
        v = VERDICT_ALIVE
    elif none and not running:
        v = VERDICT_NOT_ALIVE
    else:
        v = VERDICT_UNDECIDABLE
    return Verdict(verdict=v, cpu_delta=cpu_delta, byte_growth=byte_growth, running=running)


def measure_pair(live, finished, *, window_seconds: float = EVIDENCE_WINDOW_SECONDS):
    import time
    a0 = observe(live)
    b0 = observe(finished)
    time.sleep(float(window_seconds))
    a1 = observe(live)
    b1 = observe(finished)
    return classify(a0, a1, window_seconds=window_seconds), classify(b0, b1, window_seconds=window_seconds)


def stall_versus_finished(stalled_r: Verdict, finished_r: Verdict) -> str:
    if stalled_r.verdict == finished_r.verdict:
        return VERDICT_UNDECIDABLE
    if stalled_r.verdict == VERDICT_UNDECIDABLE:
        return VERDICT_UNDECIDABLE
    return VERDICT_UNDECIDABLE
