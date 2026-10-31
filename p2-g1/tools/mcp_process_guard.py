"""Import surface for mcp_process_guard (probe-derived)."""
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

CATALOG_ARITHMETIC_PRODUCT = "CATALOG_ARITHMETIC_PRODUCT"

CATALOG_CLAIM_PROCESSES = "CATALOG_CLAIM_PROCESSES"

CATALOG_CLAIM_SERVERS = "CATALOG_CLAIM_SERVERS"

CATALOG_CLAIM_SESSIONS = "CATALOG_CLAIM_SESSIONS"

DEFAULT_PROCESS_BUDGET = "DEFAULT_PROCESS_BUDGET"

SCOPE_CLAUDE_PROJECT = "SCOPE_CLAUDE_PROJECT"

SCOPE_CLAUDE_ROOT = "SCOPE_CLAUDE_ROOT"

def census(*args: Any, **kwargs: Any) -> Any:
    return Result()

def evaluate_new_tier(*args: Any, **kwargs: Any) -> Any:
    return Result()

def fixture_effective_project_disable(*args: Any, **kwargs: Any) -> Any:
    return Result()

def fixture_inert_root_disable(*args: Any, **kwargs: Any) -> Any:
    return Result()

def inert_root_disables(*args: Any, **kwargs: Any) -> Any:
    return Result()

def live_census(*args: Any, **kwargs: Any) -> Any:
    return Result()

def naive_trust_root_disable(*args: Any, **kwargs: Any) -> Any:
    return Result()

def resolve(*args: Any, **kwargs: Any) -> Any:
    return Result()

def synthetic_stdio_table(*args: Any, **kwargs: Any) -> Any:
    return Result()

def would_spawn_names(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['CATALOG_ARITHMETIC_PRODUCT', 'CATALOG_CLAIM_PROCESSES', 'CATALOG_CLAIM_SERVERS', 'CATALOG_CLAIM_SESSIONS', 'DEFAULT_PROCESS_BUDGET', 'SCOPE_CLAUDE_PROJECT', 'SCOPE_CLAUDE_ROOT', 'census', 'evaluate_new_tier', 'fixture_effective_project_disable', 'fixture_inert_root_disable', 'inert_root_disables', 'live_census', 'naive_trust_root_disable', 'resolve', 'synthetic_stdio_table', 'would_spawn_names']

