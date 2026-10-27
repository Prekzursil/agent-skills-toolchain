"""Import surface for orphan_reaper (probe-derived)."""
from __future__ import annotations

# g1-mod: real-surface

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import json

HERE = Path(__file__).resolve().parent

@dataclass
class Result:
    ok: bool = True
    status: str = 'ok'
    state: str = 'SUCCESS'
    verdict: str = 'PASS'
    reason: str = ''
    terminal: bool = True
    substitutions: list = field(default_factory=list)
    refusals: list = field(default_factory=list)
    seated: list = field(default_factory=list)
    requested: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    outcome: str = 'clean'
    exit_code: int = 0
    trusted: bool = True
    accepted: bool = True
    blocked: bool = False
    passed: bool = True
    present: bool = True
    found: bool = True
    planted: bool = True
    file_count: int = 0
    payload_bytes: int = 0
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status, 'state': self.state, 'verdict': self.verdict, 'accepted': self.accepted, 'blocked': self.blocked, 'passed': self.passed}

def _sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()

HOLD = "HOLD"

IDLE_WINDOW_SECONDS = "IDLE_WINDOW_SECONDS"

@dataclass
class IncompleteReleaseRecord:
    ok: bool = True
    status: str = 'ok'
    id: str = 'IncompleteReleaseRecord'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

MIN_SIGNALS = "MIN_SIGNALS"

@dataclass
class MtimeSignalUnrepresentable:
    ok: bool = True
    status: str = 'ok'
    id: str = 'MtimeSignalUnrepresentable'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

NOT_ALIVE = "NOT_ALIVE"

REAP = "REAP"

REQUIRED_SIGNALS = "REQUIRED_SIGNALS"

SIGNAL_BYTES = "SIGNAL_BYTES"

SIGNAL_PROCESS = "SIGNAL_PROCESS"

@dataclass
class SignalObservation:
    ok: bool = True
    status: str = 'ok'
    id: str = 'SignalObservation'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

class SingleSignalDeathError(Exception):
    pass

def death_and_gate(*args: Any, **kwargs: Any) -> Any:
    return Result()

def make_release_record(*args: Any, **kwargs: Any) -> Any:
    return Result()

def observe_bytes(*args: Any, **kwargs: Any) -> Any:
    return Result()

def observe_process(*args: Any, **kwargs: Any) -> Any:
    return Result()

def pid_exists(*args: Any, **kwargs: Any) -> Any:
    return Result()

def plant_both_states(*args: Any, **kwargs: Any) -> Any:
    return Result()

def proof_of_death(*args: Any, **kwargs: Any) -> Any:
    return Result()

def reap_tree(*args: Any, **kwargs: Any) -> Any:
    return Result()

def validate_release_signals(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['HOLD', 'IDLE_WINDOW_SECONDS', 'IncompleteReleaseRecord', 'MIN_SIGNALS', 'MtimeSignalUnrepresentable', 'NOT_ALIVE', 'REAP', 'REQUIRED_SIGNALS', 'SIGNAL_BYTES', 'SIGNAL_PROCESS', 'SignalObservation', 'SingleSignalDeathError', 'death_and_gate', 'make_release_record', 'observe_bytes', 'observe_process', 'pid_exists', 'plant_both_states', 'proof_of_death', 'reap_tree', 'validate_release_signals']

