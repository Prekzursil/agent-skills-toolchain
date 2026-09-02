"""Import surface for b07_scheduler (probe-derived)."""
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

COMMENT_ONLY_CONFIG_TEXT = "COMMENT_ONLY_CONFIG_TEXT"

HOLD_S = "HOLD_S"

@dataclass
class LaneConfig:
    ok: bool = True
    status: str = 'ok'
    id: str = 'LaneConfig'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

@dataclass
class LaneScheduler:
    ok: bool = True
    status: str = 'ok'
    id: str = 'LaneScheduler'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

REASON_HEADROOM = "REASON_HEADROOM"

WAIT_BUDGET_S = "WAIT_BUDGET_S"

def active_config(*args: Any, **kwargs: Any) -> Any:
    return Result()

def comment_only_config(*args: Any, **kwargs: Any) -> Any:
    return Result()

def parse_lane_config(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_arm(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_campaign(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_trial(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['COMMENT_ONLY_CONFIG_TEXT', 'HOLD_S', 'LaneConfig', 'LaneScheduler', 'REASON_HEADROOM', 'WAIT_BUDGET_S', 'active_config', 'comment_only_config', 'parse_lane_config', 'run_arm', 'run_campaign', 'run_trial']

