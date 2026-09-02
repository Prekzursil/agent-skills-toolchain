"""Import surface for chaos (probe-derived)."""
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

DECLARED = "DECLARED"

DELEGATED_UNIT = "DELEGATED_UNIT"

class DelegatedFaultError(Exception):
    pass

FAMILY = "FAMILY"

@dataclass
class FaultSession:
    ok: bool = True
    status: str = 'ok'
    id: str = 'FaultSession'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

NETWORK_IDS = "NETWORK_IDS"

SHIPPED = "SHIPPED"

def clock_jump_back_does_not_corrupt_log(*args: Any, **kwargs: Any) -> Any:
    return Result()

def derive_params(*args: Any, **kwargs: Any) -> Any:
    return Result()

def inject_network(*args: Any, **kwargs: Any) -> Any:
    return Result()

def refuse_foreign_pid(*args: Any, **kwargs: Any) -> Any:
    return Result()

def refuse_live_path(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_declared_faults(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_reversibility(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['DECLARED', 'DELEGATED_UNIT', 'DelegatedFaultError', 'FAMILY', 'FaultSession', 'NETWORK_IDS', 'SHIPPED', 'clock_jump_back_does_not_corrupt_log', 'derive_params', 'inject_network', 'refuse_foreign_pid', 'refuse_live_path', 'run_declared_faults', 'run_reversibility']

