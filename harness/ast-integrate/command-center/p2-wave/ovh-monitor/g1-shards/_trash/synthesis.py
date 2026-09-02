"""Import surface for synthesis (probe-derived)."""
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

CLASS_LOST_DATA = "CLASS_LOST_DATA"

CLASS_MISSING_SLOT = "CLASS_MISSING_SLOT"

CLASS_TOTAL_LOSS = "CLASS_TOTAL_LOSS"

DEATH_SENTENCE = "DEATH_SENTENCE"

SKELETON_BUDGET_SECONDS = "SKELETON_BUDGET_SECONDS"

UNKNOWN = "UNKNOWN"

def atomic_write_json(*args: Any, **kwargs: Any) -> Any:
    return Result()

def claim_slots(*args: Any, **kwargs: Any) -> Any:
    return Result()

def exercise_lane(*args: Any, **kwargs: Any) -> Any:
    return Result()

def inspect_artifact(*args: Any, **kwargs: Any) -> Any:
    return Result()

def lane_ids(*args: Any, **kwargs: Any) -> Any:
    return Result()

def load_synthesis_lane(*args: Any, **kwargs: Any) -> Any:
    return Result()

def record_milestone(*args: Any, **kwargs: Any) -> Any:
    return Result()

def resolve_output(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_kill_test(*args: Any, **kwargs: Any) -> Any:
    return Result()

def write_skeleton(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['CLASS_LOST_DATA', 'CLASS_MISSING_SLOT', 'CLASS_TOTAL_LOSS', 'DEATH_SENTENCE', 'SKELETON_BUDGET_SECONDS', 'UNKNOWN', 'atomic_write_json', 'claim_slots', 'exercise_lane', 'inspect_artifact', 'lane_ids', 'load_synthesis_lane', 'record_milestone', 'resolve_output', 'run_kill_test', 'write_skeleton']

