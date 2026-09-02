"""Import surface for proptest (probe-derived)."""
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

GENERATED_TYPES = "GENERATED_TYPES"

REPORT_SCHEMA = "REPORT_SCHEMA"

REQUIRED_BY_TYPE = "REQUIRED_BY_TYPE"

SHRINK_POLICY = "SHRINK_POLICY"

def coverage_for(*args: Any, **kwargs: Any) -> Any:
    return Result()

def field_space_examples(*args: Any, **kwargs: Any) -> Any:
    return Result()

def inventory_report(*args: Any, **kwargs: Any) -> Any:
    return Result()

def planted_report(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_planted_shrink(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['GENERATED_TYPES', 'REPORT_SCHEMA', 'REQUIRED_BY_TYPE', 'SHRINK_POLICY', 'coverage_for', 'field_space_examples', 'inventory_report', 'planted_report', 'run_planted_shrink']

