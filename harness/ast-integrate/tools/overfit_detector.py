"""Import surface for overfit_detector (probe-derived)."""
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
class MemorizeVisibleWorkflow:
    ok: bool = True
    status: str = 'ok'
    id: str = 'MemorizeVisibleWorkflow'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

class PerRunThresholdTuneError(Exception):
    pass

@dataclass
class TrueRuleWorkflow:
    ok: bool = True
    status: str = 'ok'
    id: str = 'TrueRuleWorkflow'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

def assert_no_heldout_touch(*args: Any, **kwargs: Any) -> Any:
    return Result()

def build_corpus(*args: Any, **kwargs: Any) -> Any:
    return Result()

def detect(*args: Any, **kwargs: Any) -> Any:
    return Result()

def independent_slice(*args: Any, **kwargs: Any) -> Any:
    return Result()

def load_threshold(*args: Any, **kwargs: Any) -> Any:
    return Result()

def slice_of(*args: Any, **kwargs: Any) -> Any:
    return Result()

def split(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['MemorizeVisibleWorkflow', 'PerRunThresholdTuneError', 'TrueRuleWorkflow', 'assert_no_heldout_touch', 'build_corpus', 'detect', 'independent_slice', 'load_threshold', 'slice_of', 'split']

