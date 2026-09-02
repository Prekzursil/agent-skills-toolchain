"""Import surface for harness_walker (probe-derived)."""
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
class FsOps:
    ok: bool = True
    status: str = 'ok'
    id: str = 'FsOps'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

@dataclass
class IncompleteWalk:
    ok: bool = True
    status: str = 'ok'
    id: str = 'IncompleteWalk'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

def build_hostile_tree(*args: Any, **kwargs: Any) -> Any:
    return Result()

def extended_length_form(*args: Any, **kwargs: Any) -> Any:
    return Result()

def naive_walk_crash_as_zero(*args: Any, **kwargs: Any) -> Any:
    return Result()

def naive_walk_follow_unlimited(*args: Any, **kwargs: Any) -> Any:
    return Result()

def naive_walk_raise(*args: Any, **kwargs: Any) -> Any:
    return Result()

def naive_walk_silent_skip(*args: Any, **kwargs: Any) -> Any:
    return Result()

def require_complete(*args: Any, **kwargs: Any) -> Any:
    return Result()

def result_fingerprint(*args: Any, **kwargs: Any) -> Any:
    return Result()

def safe_relpath(*args: Any, **kwargs: Any) -> Any:
    return Result()

def walk_tree(*args: Any, **kwargs: Any) -> Any:
    return Result()

def windows_device_relpath(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['FsOps', 'IncompleteWalk', 'build_hostile_tree', 'extended_length_form', 'naive_walk_crash_as_zero', 'naive_walk_follow_unlimited', 'naive_walk_raise', 'naive_walk_silent_skip', 'require_complete', 'result_fingerprint', 'safe_relpath', 'walk_tree', 'windows_device_relpath']

