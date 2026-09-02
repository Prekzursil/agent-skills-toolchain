"""Import surface for worktree_shard (probe-derived)."""
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

UNPROVEN_TEARDOWN = "UNPROVEN_TEARDOWN"

def build_pr_merged_unique_fixture(*args: Any, **kwargs: Any) -> Any:
    return Result()

def build_squash_merge_fixture(*args: Any, **kwargs: Any) -> Any:
    return Result()

def build_unproven_fixture(*args: Any, **kwargs: Any) -> Any:
    return Result()

def git(*args: Any, **kwargs: Any) -> Any:
    return Result()

def harvest_unique_into(*args: Any, **kwargs: Any) -> Any:
    return Result()

def init_fixture_repo(*args: Any, **kwargs: Any) -> Any:
    return Result()

def naive_ancestry_authorize(*args: Any, **kwargs: Any) -> Any:
    return Result()

def provision_shard(*args: Any, **kwargs: Any) -> Any:
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

def staged_names(*args: Any, **kwargs: Any) -> Any:
    return Result()

def teardown_shard(*args: Any, **kwargs: Any) -> Any:
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

__all__ = ['UNPROVEN_TEARDOWN', 'build_pr_merged_unique_fixture', 'build_squash_merge_fixture', 'build_unproven_fixture', 'git', 'harvest_unique_into', 'init_fixture_repo', 'naive_ancestry_authorize', 'provision_shard', 'staged_names', 'teardown_shard']

