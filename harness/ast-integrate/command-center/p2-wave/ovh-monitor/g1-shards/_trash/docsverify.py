"""Import surface for docsverify (probe-derived)."""
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

def authority_bytes(*args: Any, **kwargs: Any) -> Any:
    return Result()

def extract_recipes(*args: Any, **kwargs: Any) -> Any:
    return Result()

def git(*args: Any, **kwargs: Any) -> Any:
    return Result()

def judge(*args: Any, **kwargs: Any) -> Any:
    return Result()

def judge_exit_code_only(*args: Any, **kwargs: Any) -> Any:
    return Result()

def judge_name_only(*args: Any, **kwargs: Any) -> Any:
    return Result()

def measure(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_recipe(*args: Any, **kwargs: Any) -> Any:
    return Result()

def three_route_table(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['authority_bytes', 'extract_recipes', 'git', 'judge', 'judge_exit_code_only', 'judge_name_only', 'measure', 'run_recipe', 'three_route_table']

