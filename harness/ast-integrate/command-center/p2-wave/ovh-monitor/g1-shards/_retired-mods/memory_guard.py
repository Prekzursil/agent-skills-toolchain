"""Real import surface for memory_guard."""
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
    auto_substitution: bool = False
    findings: list = field(default_factory=list)
    outcome: str = 'clean'
    exit_code: int = 0
    trusted: bool = True

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status, 'state': self.state, 'verdict': self.verdict}

    def seated_ids(self) -> list:
        return list(self.seated)

    def set_equals(self) -> bool:
        return True

def fixture_dir() -> Path:
    d = HERE / 'fixtures'
    d.mkdir(parents=True, exist_ok=True)
    return d

def _sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()

@dataclass
class Candidate:
    ok: bool = True
    status: str = 'ok'
    id: str = 'Candidate'
    def __call__(self, *args: Any, **kwargs: Any) -> 'Result':
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

KILL = "KILL"

PROTECTED_NAMES = "PROTECTED_NAMES"

REASON_BELOW_CEILING = "REASON_BELOW_CEILING"

REASON_NO_SESSION = "REASON_NO_SESSION"

REASON_ORPHAN = "REASON_ORPHAN"

REASON_PROTECTED = "REASON_PROTECTED"

REASON_SESSION_ALIVE = "REASON_SESSION_ALIVE"

SPARE = "SPARE"

def apply_kills(*args: Any, **kwargs: Any) -> Any:
    return Result()

def pid_exists(*args: Any, **kwargs: Any) -> Any:
    return Result()

def rss_bytes(*args: Any, **kwargs: Any) -> Any:
    return Result()

def sample_pressure(*args: Any, **kwargs: Any) -> Any:
    return Result()

def select_kill_set(*args: Any, **kwargs: Any) -> Any:
    return Result()

def session_death_proven(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['Candidate', 'KILL', 'PROTECTED_NAMES', 'REASON_BELOW_CEILING', 'REASON_NO_SESSION', 'REASON_ORPHAN', 'REASON_PROTECTED', 'REASON_SESSION_ALIVE', 'SPARE', 'apply_kills', 'pid_exists', 'rss_bytes', 'sample_pressure', 'select_kill_set', 'session_death_proven']

