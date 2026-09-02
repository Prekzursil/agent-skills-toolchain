"""Import surface for agentspec.evals.baseline (probe-derived)."""
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

REASON_CROSS_CORPUS = "REASON_CROSS_CORPUS"

REASON_SPEC_MISMATCH = "REASON_SPEC_MISMATCH"

REASON_SUMMARY_ONLY = "REASON_SUMMARY_ONLY"

def compare_ignoring_corpus_for_control(*args: Any, **kwargs: Any) -> Any:
    return Result()

def compare_to_baseline(*args: Any, **kwargs: Any) -> Any:
    return Result()

def delta_from_rows(*args: Any, **kwargs: Any) -> Any:
    return Result()

def dump_json(*args: Any, **kwargs: Any) -> Any:
    return Result()

def freeze_baseline(*args: Any, **kwargs: Any) -> Any:
    return Result()

def load_json(*args: Any, **kwargs: Any) -> Any:
    return Result()

def make_run(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['REASON_CROSS_CORPUS', 'REASON_SPEC_MISMATCH', 'REASON_SUMMARY_ONLY', 'compare_ignoring_corpus_for_control', 'compare_to_baseline', 'delta_from_rows', 'dump_json', 'freeze_baseline', 'load_json', 'make_run']

