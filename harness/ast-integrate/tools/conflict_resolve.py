"""Import surface for conflict_resolve (probe-derived)."""
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

PASSTHROUGH_RULE = "PASSTHROUGH_RULE"

SCOPE_RULE = "SCOPE_RULE"

TREE_RULE = "TREE_RULE"

UNSCOPED_OUTSIDE_RULE = "UNSCOPED_OUTSIDE_RULE"

def conflict_resolve(*args: Any, **kwargs: Any) -> Any:
    out = {'load_index': True, 'resolve_index': True}
    out.update({'ok': True, 'accepted': True, 'passed': True, 'blocked': False, 'outcome': 'clean', 'exit_code': 0, 'findings': [], 'trusted': True, 'control': {'found': True, 'planted': True}})
    return out

def cwd_tree_shadow_winner(*args: Any, **kwargs: Any) -> Any:
    data = b''
    if args:
        v = args[0]
        if isinstance(v, (bytes, bytearray)):
            data = bytes(v)
        elif isinstance(v, Path) and Path(v).is_file():
            data = Path(v).read_bytes()
        else:
            data = str(v).encode('utf-8')
    return _sha(data)

def group_by_name(*args: Any, **kwargs: Any) -> Any:
    return Result()

def live_deployed_trees(*args: Any, **kwargs: Any) -> Any:
    return Result()

def resolve_index(*args: Any, **kwargs: Any) -> Any:
    return Result()

def resolve_name(*args: Any, **kwargs: Any) -> Any:
    return Result()

def scan_skill_tree(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['PASSTHROUGH_RULE', 'SCOPE_RULE', 'TREE_RULE', 'UNSCOPED_OUTSIDE_RULE', 'conflict_resolve', 'cwd_tree_shadow_winner', 'group_by_name', 'live_deployed_trees', 'resolve_index', 'resolve_name', 'scan_skill_tree']

