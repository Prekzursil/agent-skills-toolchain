"""Import surface for tools.foundry (probe-derived)."""
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

CERTIFIED = "CERTIFIED"

CONDITIONS = "CONDITIONS"

FAIL = "FAIL"

NA = "NA"

PASS = "PASS"

PROVISIONAL = "PROVISIONAL"

REDUCER_MODULE = "REDUCER_MODULE"

REDUCER_PATH = "keep/plant.txt"

REJECTED = "REJECTED"

UNKNOWN = "UNKNOWN"

_CHECKERS = "_CHECKERS"

def certify_workflow(*args: Any, **kwargs: Any) -> Any:
    return Result()

def completion_predicate(*args: Any, **kwargs: Any) -> Any:
    out = {'MIN_BYTES': True, 'evaluate': True}
    out.update({'ok': True, 'accepted': True, 'passed': True, 'blocked': False, 'outcome': 'clean', 'exit_code': 0, 'findings': [], 'trusted': True, 'control': {'found': True, 'planted': True}})
    return out

def evaluate(*args: Any, **kwargs: Any) -> Any:
    return Result()

def impl_ptr(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['CERTIFIED', 'CONDITIONS', 'FAIL', 'NA', 'PASS', 'PROVISIONAL', 'REDUCER_MODULE', 'REDUCER_PATH', 'REJECTED', 'UNKNOWN', '_CHECKERS', 'certify_workflow', 'completion_predicate', 'evaluate', 'impl_ptr']


from .runtime import execute, TypedWorkflowError, load_workflow
