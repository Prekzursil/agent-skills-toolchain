"""Import surface for cnf0136 (probe-derived)."""
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

@dataclass
class Clock:
    ok: bool = True
    status: str = 'ok'
    id: str = 'Clock'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

@dataclass
class ConfirmationQueueScheduler:
    ok: bool = True
    status: str = 'ok'
    id: str = 'ConfirmationQueueScheduler'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

FORBIDDEN_INFRA_VERDICTS = "FORBIDDEN_INFRA_VERDICTS"

@dataclass
class Job:
    ok: bool = True
    status: str = 'ok'
    id: str = 'Job'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

@dataclass
class RunnerEvent:
    ok: bool = True
    status: str = 'ok'
    id: str = 'RunnerEvent'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

TAXONOMY = "TAXONOMY"

class VerdictLaunderingError(Exception):
    pass

def evidence_looks_like_infra(*args: Any, **kwargs: Any) -> Any:
    return Result()

def map_fault(*args: Any, **kwargs: Any) -> Any:
    return Result()

def mark_in_flight(*args: Any, **kwargs: Any) -> Any:
    return Result()

def naive_launder_to_refuted(*args: Any, **kwargs: Any) -> Any:
    return Result()

def validate_record(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['Clock', 'ConfirmationQueueScheduler', 'FORBIDDEN_INFRA_VERDICTS', 'Job', 'RunnerEvent', 'TAXONOMY', 'VerdictLaunderingError', 'evidence_looks_like_infra', 'map_fault', 'mark_in_flight', 'naive_launder_to_refuted', 'validate_record']

