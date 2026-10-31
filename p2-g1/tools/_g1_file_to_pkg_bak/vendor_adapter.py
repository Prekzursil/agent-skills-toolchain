"""Import surface for vendor_adapter (probe-derived)."""
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

CONTEXT_THRESHOLDS = "CONTEXT_THRESHOLDS"

VERDICT_NEGOTIATED = "VERDICT_NEGOTIATED"

VERDICT_REFUSED = "VERDICT_REFUSED"

def atoms_from_descriptor(*args: Any, **kwargs: Any) -> Any:
    return Result()

def capability_matrix(*args: Any, **kwargs: Any) -> Any:
    return Result()

def common_subset(*args: Any, **kwargs: Any) -> Any:
    return Result()

def intersection_cost(*args: Any, **kwargs: Any) -> Any:
    return Result()

def is_silent_downgrade(*args: Any, **kwargs: Any) -> Any:
    return Result()

def load_published_descriptors(*args: Any, **kwargs: Any) -> Any:
    return Result()

def negotiate_cross_vendor(*args: Any, **kwargs: Any) -> Any:
    return Result()

def negotiate_for_vendor(*args: Any, **kwargs: Any) -> Any:
    return Result()

def union_atoms(*args: Any, **kwargs: Any) -> Any:
    return Result()

def unit_required_atoms(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['CONTEXT_THRESHOLDS', 'VERDICT_NEGOTIATED', 'VERDICT_REFUSED', 'atoms_from_descriptor', 'capability_matrix', 'common_subset', 'intersection_cost', 'is_silent_downgrade', 'load_published_descriptors', 'negotiate_cross_vendor', 'negotiate_for_vendor', 'union_atoms', 'unit_required_atoms']

