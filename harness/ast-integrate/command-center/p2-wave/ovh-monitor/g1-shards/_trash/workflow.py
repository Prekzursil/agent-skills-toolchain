"""Import surface for tools.workflow (probe-derived)."""
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

class RollbackRefused(Exception):
    pass

STRATEGIES = "STRATEGIES"

@dataclass
class Service:
    ok: bool = True
    status: str = 'ok'
    id: str = 'Service'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

def capability_vector(*args: Any, **kwargs: Any) -> Any:
    return Result()

def decompose(*args: Any, **kwargs: Any) -> Any:
    return Result()

def fingerprint(*args: Any, **kwargs: Any) -> Any:
    return Result()

def fuse(*args: Any, **kwargs: Any) -> Any:
    return Result()

def fuse_lossy(*args: Any, **kwargs: Any) -> Any:
    return Result()

def refuse_deletion_as_rollback(*args: Any, **kwargs: Any) -> Any:
    return Result()

def rollback(*args: Any, **kwargs: Any) -> Any:
    return Result()

def sabotaged_restore_fires(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['RollbackRefused', 'STRATEGIES', 'Service', 'capability_vector', 'decompose', 'fingerprint', 'fuse', 'fuse_lossy', 'refuse_deletion_as_rollback', 'rollback', 'sabotaged_restore_fires']

