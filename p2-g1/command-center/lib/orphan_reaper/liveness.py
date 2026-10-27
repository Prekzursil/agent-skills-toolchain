"""Two-signal death gate: process table AND byte growth. mtime is unrepresentable."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

HOLD = "HOLD"
REAP = "REAP"
NOT_ALIVE = "NOT_ALIVE"
SIGNAL_PROCESS = "process"
SIGNAL_BYTES = "bytes"
IDLE_WINDOW_SECONDS = 20 * 60
MIN_SIGNALS = 2
REQUIRED_SIGNALS = (SIGNAL_PROCESS, SIGNAL_BYTES)


class IncompleteReleaseRecord(ValueError):
    pass


class MtimeSignalUnrepresentable(ValueError):
    pass


class SingleSignalDeathError(ValueError):
    pass


@dataclass
class SignalObservation:
    name: str
    verdict: str
    values: dict


def observe_process(pid: int, *, pid_exists_now: bool, cpu_delta_ns: int = 0) -> dict:
    alive = bool(pid_exists_now)
    return {
        "name": SIGNAL_PROCESS,
        "verdict": "ALIVE" if alive else NOT_ALIVE,
        "pid_exists": alive,
        "cpu_delta_ns": int(cpu_delta_ns),
        "pid": int(pid),
    }


def observe_bytes(bytes_t0: int, bytes_t1: int) -> dict:
    delta = int(bytes_t1) - int(bytes_t0)
    alive = delta > 0
    return {
        "name": SIGNAL_BYTES,
        "verdict": "ALIVE" if alive else NOT_ALIVE,
        "delta": delta,
        "bytes_t0": int(bytes_t0),
        "bytes_t1": int(bytes_t1),
    }


def validate_release_signals(signals: list[dict[str, Any]]) -> None:
    names = [s.get("name") for s in signals]
    if "mtime" in names:
        raise MtimeSignalUnrepresentable("mtime cannot enter the death gate")
    if len(signals) < MIN_SIGNALS or set(names) != set(REQUIRED_SIGNALS):
        raise IncompleteReleaseRecord(f"need {REQUIRED_SIGNALS}, got {names}")
    if sum(1 for s in signals if s.get("verdict") == NOT_ALIVE) == 1 and all(
        s.get("verdict") in {"ALIVE", NOT_ALIVE} for s in signals
    ):
        if any(s.get("verdict") == "ALIVE" for s in signals):
            raise SingleSignalDeathError("one-signal death is refused")


def proof_of_death(signals: list[dict[str, Any]]) -> bool:
    validate_release_signals(signals)
    return all(s.get("verdict") == NOT_ALIVE for s in signals)


def death_and_gate(process_alive: bool, bytes_grew: bool) -> str:
    if (not process_alive) and (not bytes_grew):
        return REAP
    return HOLD
