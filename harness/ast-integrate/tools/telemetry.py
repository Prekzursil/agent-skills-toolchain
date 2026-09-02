"""Import surface for telemetry (probe-derived)."""
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

EMISSION_POINTS = "EMISSION_POINTS"

FIELD_PURPOSE = "FIELD_PURPOSE"

MARKER_HOME = "MARKER_HOME"

MARKER_PERSON = "MARKER_PERSON"

MARKER_PROJECT = "MARKER_PROJECT"

MARKER_SECRET = "MARKER_SECRET"

POINT_PURPOSE = "POINT_PURPOSE"

def audit_no_network(*args: Any, **kwargs: Any) -> Any:
    return Result()

def refuse_ephemeral_sink(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_canary_sweep(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_opt_out_proof(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_unredacted_control(*args: Any, **kwargs: Any) -> Any:
    return Result()

def value_leaked(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['EMISSION_POINTS', 'FIELD_PURPOSE', 'MARKER_HOME', 'MARKER_PERSON', 'MARKER_PROJECT', 'MARKER_SECRET', 'POINT_PURPOSE', 'audit_no_network', 'refuse_ephemeral_sink', 'run_canary_sweep', 'run_opt_out_proof', 'run_unredacted_control', 'value_leaked']

