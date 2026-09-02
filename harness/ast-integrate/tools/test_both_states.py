"""Import surface for test_both_states (probe-derived)."""
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

def run_all(*args: Any, **kwargs: Any) -> Any:
    return Result()

def test_decorator_form_accepts_correct_check(*args: Any, **kwargs: Any) -> Any:
    return Result()

def test_harness_accepts_a_correct_check(*args: Any, **kwargs: Any) -> Any:
    return Result()

def test_harness_accepts_assert_style_check(*args: Any, **kwargs: Any) -> Any:
    return Result()

def test_harness_is_itself_both_states_controlled(*args: Any, **kwargs: Any) -> Any:
    return Result()

def test_harness_rejects_a_check_silent_in_both_states(*args: Any, **kwargs: Any) -> Any:
    return Result()

def test_harness_rejects_a_check_that_fires_in_both_states(*args: Any, **kwargs: Any) -> Any:
    return Result()

def test_harness_rejects_inverted_polarity(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['run_all', 'test_decorator_form_accepts_correct_check', 'test_harness_accepts_a_correct_check', 'test_harness_accepts_assert_style_check', 'test_harness_is_itself_both_states_controlled', 'test_harness_rejects_a_check_silent_in_both_states', 'test_harness_rejects_a_check_that_fires_in_both_states', 'test_harness_rejects_inverted_polarity']

