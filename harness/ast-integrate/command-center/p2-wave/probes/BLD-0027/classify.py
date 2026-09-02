"""Two-signal timeout/stillness reducer (BLD-0027).

Liveness requires two independent process signals (CPU delta AND artifact
byte growth). File mtime is never a liveness input. Timeout is FAILED,
never SUCCESS. A dead monitor with live remote work is SEVERED.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

FAILED = "FAILED"
SEVERED = "SEVERED"
SUCCESS = "SUCCESS"
ALIVE = "ALIVE"
ALIVE_QUIET = "ALIVE-QUIET"
FINISHED = "FINISHED"
UNDECIDABLE = "UNDECIDABLE"
STALLED = "STALLED"

ORCH_RUNNING = "RUNNING"
ORCH_FINISHED = "FINISHED"


@dataclass
class Observation:
    timed_out: bool = False
    exit_code: int | None = None
    artifact_exists: bool = False
    cpu_delta: int = 0
    byte_delta: int = 0
    heartbeat_delta: int = 0
    work_alive: bool | None = None
    monitor_pid_alive: bool | None = None
    orchestrator_state: str | None = None
    mtime_age_s: float | None = None
    stall_window_s: float = 0.4
    notes: dict[str, Any] = field(default_factory=dict)

    @property
    def two_signal_live(self) -> bool:
        return self.cpu_delta > 0 and self.byte_delta > 0

    @property
    def monitor_reachable(self) -> bool:
        return self.heartbeat_delta > 0


def classify(obs: Observation) -> str:
    """Typed verdict. Observation.mtime_age_s is never read."""
    if obs.timed_out:
        return FAILED
    if obs.exit_code == 0 and not obs.artifact_exists:
        return FAILED
    work_live = obs.two_signal_live or (
        obs.work_alive is True and obs.cpu_delta > 0
    )
    if not obs.monitor_reachable and work_live:
        return SEVERED
    if obs.orchestrator_state == ORCH_FINISHED:
        return FINISHED
    if obs.cpu_delta > 0 and obs.byte_delta <= 0:
        if obs.orchestrator_state == ORCH_RUNNING:
            return ALIVE_QUIET
        return UNDECIDABLE
    if obs.two_signal_live and obs.monitor_reachable:
        return ALIVE
    if obs.cpu_delta <= 0 and obs.byte_delta <= 0:
        if obs.orchestrator_state == ORCH_RUNNING:
            return UNDECIDABLE
        if obs.orchestrator_state == ORCH_FINISHED:
            return FINISHED
        return UNDECIDABLE
    if obs.exit_code not in (None, 0):
        return FAILED
    return UNDECIDABLE


def is_stalled(verdict: str) -> bool:
    return verdict == STALLED


def is_success(verdict: str) -> bool:
    return verdict == SUCCESS
