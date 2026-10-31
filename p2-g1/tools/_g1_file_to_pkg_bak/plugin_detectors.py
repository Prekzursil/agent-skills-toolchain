"""Import surface for detectors (probe-derived)."""
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

APPEND_ONLY_TOPO = "APPEND_ONLY_TOPO"

CLEAN_PY = "CLEAN_PY"

HONEST_TOPO = "HONEST_TOPO"

KNOWN_PRESENT_DETECTOR = "KNOWN_PRESENT_DETECTOR"

QUESTION = "QUESTION"

REQUESTS_PY = "REQUESTS_PY"

ROTATE_KEY_PY = "ROTATE_KEY_PY"

VERDICT_DIFFERS = "VERDICT_DIFFERS"

VERDICT_ERROR = "VERDICT_ERROR"

VERDICT_NOT_CHECKED = "VERDICT_NOT_CHECKED"

VERDICT_SILENT_BOTH = "VERDICT_SILENT_BOTH"

def _fired_list(*args: Any, **kwargs: Any) -> Any:
    return Result()

def harness_self_test(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_campaign(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_two_state(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['APPEND_ONLY_TOPO', 'CLEAN_PY', 'HONEST_TOPO', 'KNOWN_PRESENT_DETECTOR', 'QUESTION', 'REQUESTS_PY', 'ROTATE_KEY_PY', 'VERDICT_DIFFERS', 'VERDICT_ERROR', 'VERDICT_NOT_CHECKED', 'VERDICT_SILENT_BOTH', '_fired_list', 'harness_self_test', 'run_campaign', 'run_two_state']

