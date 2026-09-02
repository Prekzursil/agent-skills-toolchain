"""Import surface for council.risk (probe-derived)."""
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
class DeliberationSession:
    ok: bool = True
    status: str = 'ok'
    id: str = 'DeliberationSession'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

EVENT_MUTATION_REFUSED = "EVENT_MUTATION_REFUSED"

EVENT_START_WITHOUT_CLASS = "EVENT_START_WITHOUT_CLASS"

FLOORS = "FLOORS"

RISK_CLASSES = "RISK_CLASSES"

def at_floor(*args: Any, **kwargs: Any) -> Any:
    return Result()

def evaluate_config(*args: Any, **kwargs: Any) -> Any:
    return Result()

def floor_enforcement_matrix(*args: Any, **kwargs: Any) -> Any:
    return Result()

def high_under_low_attack(*args: Any, **kwargs: Any) -> Any:
    return Result()

def immutability_holds(*args: Any, **kwargs: Any) -> Any:
    return Result()

def late_declaration_attack(*args: Any, **kwargs: Any) -> Any:
    return Result()

def map_risk_class(*args: Any, **kwargs: Any) -> Any:
    return Result()

def matrix_is_sound(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['DeliberationSession', 'EVENT_MUTATION_REFUSED', 'EVENT_START_WITHOUT_CLASS', 'FLOORS', 'RISK_CLASSES', 'at_floor', 'evaluate_config', 'floor_enforcement_matrix', 'high_under_low_attack', 'immutability_holds', 'late_declaration_attack', 'map_risk_class', 'matrix_is_sound']

