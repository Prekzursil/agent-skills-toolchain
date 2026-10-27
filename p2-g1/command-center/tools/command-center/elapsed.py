"""Monotonic elapsed classification. Wall-clock sources are forbidden here."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class UnitTimes:
    unit_id: str
    started_s: float
    last_progress_s: float
    timeout_s: float
    stall_after_s: float = 2.0

    def __init__(
        self,
        unit_id: str,
        started_s: float,
        last_progress_s: float,
        timeout_s: float,
        stall_after_s: float = 2.0,
    ) -> None:
        self.unit_id = unit_id
        self.started_s = float(started_s)
        self.last_progress_s = float(last_progress_s)
        self.timeout_s = float(timeout_s)
        self.stall_after_s = float(stall_after_s)


@dataclass
class Classification:
    state: str
    elapsed_s: float
    idle_s: float
    unit_id: str = ""


class FakeClock:
    def __init__(self, monotonic: float = 0.0) -> None:
        self.monotonic = float(monotonic)

    def now(self) -> float:
        return self.monotonic

    def elapse(self, seconds: float) -> None:
        self.monotonic += float(seconds)

    def sleep(self, seconds: float) -> None:
        self.elapse(seconds)


def classify(times: UnitTimes, now_s: float) -> Classification:
    elapsed = float(now_s) - float(times.started_s)
    idle = float(now_s) - float(times.last_progress_s)
    if elapsed >= float(times.timeout_s):
        state = "TIMED_OUT"
    elif idle >= float(times.stall_after_s):
        state = "STALLED"
    else:
        state = "RUNNING"
    return Classification(
        state=state,
        elapsed_s=elapsed,
        idle_s=idle,
        unit_id=times.unit_id,
    )


_WALL_RE = re.compile(
    r"\b(?:" + "time" + r"\." + "time" + r"(?:_ns)?|datetime\.(?:now|utcnow)|date\.today)\s*\("
)


def wall_clock_hits(src: str, path: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for m in _WALL_RE.finditer(src):
        token = m.group(0)
        attr = "time"
        if "time_ns" in token:
            attr = "time_ns"
        elif "utcnow" in token:
            attr = "utcnow"
        elif "datetime.now" in token:
            attr = "now"
        elif "today" in token:
            attr = "today"
        hits.append({"path": path, "attr": attr, "node": token})
    return hits
