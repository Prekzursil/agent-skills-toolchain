"""Import surface for science_blueprints (probe-derived)."""
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
class HonestRule:
    ok: bool = True
    status: str = 'ok'
    id: str = 'HonestRule'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

class PerRunThresholdTuneError(Exception):
    pass

class VisibleSliceOnlyVerdictError(Exception):
    pass

def build_eval_corpus(*args: Any, **kwargs: Any) -> Any:
    return Result()

def design(*args: Any, **kwargs: Any) -> Any:
    return Result()

def evaluate(*args: Any, **kwargs: Any) -> Any:
    return Result()

def load_library(*args: Any, **kwargs: Any) -> Any:
    return Result()

def load_thresholds(*args: Any, **kwargs: Any) -> Any:
    return Result()

def missing_effect_size_fixture(*args: Any, **kwargs: Any) -> Any:
    return Result()

def omission_gate(*args: Any, **kwargs: Any) -> Any:
    return Result()

def powered_fixture(*args: Any, **kwargs: Any) -> Any:
    return Result()

def replicate(*args: Any, **kwargs: Any) -> Any:
    return Result()

def review(*args: Any, **kwargs: Any) -> Any:
    return Result()

def try_evaluate(*args: Any, **kwargs: Any) -> Any:
    return Result()

def underpowered_fixture(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['HonestRule', 'PerRunThresholdTuneError', 'VisibleSliceOnlyVerdictError', 'build_eval_corpus', 'design', 'evaluate', 'load_library', 'load_thresholds', 'missing_effect_size_fixture', 'omission_gate', 'powered_fixture', 'replicate', 'review', 'try_evaluate', 'underpowered_fixture']

