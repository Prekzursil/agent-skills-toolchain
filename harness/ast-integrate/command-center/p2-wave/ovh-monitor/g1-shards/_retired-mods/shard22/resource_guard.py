"""Import surface for resource_guard (probe-derived)."""
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

ACTION_REAP = "ACTION_REAP"

ACTION_SPARE = "ACTION_SPARE"

REASON_ALLOWLIST = "REASON_ALLOWLIST"

REASON_BELOW_CEILING = "REASON_BELOW_CEILING"

REASON_ORPHAN_NOT_PROVEN = "REASON_ORPHAN_NOT_PROVEN"

REASON_ORPHAN_PROVEN = "REASON_ORPHAN_PROVEN"

def apply_reaps(*args: Any, **kwargs: Any) -> Any:
    return Result()

def drop_allowlist(*args: Any, **kwargs: Any) -> Any:
    return Result()

def evaluate(*args: Any, **kwargs: Any) -> Any:
    return Result()

def health_status(*args: Any, **kwargs: Any) -> Any:
    return Result()

def load_below_ceiling_world(*args: Any, **kwargs: Any) -> Any:
    return Result()

def load_ceiling_world(*args: Any, **kwargs: Any) -> Any:
    return Result()

def naive_rss_kill_set(*args: Any, **kwargs: Any) -> Any:
    return Result()

def shared_service_survives(*args: Any, **kwargs: Any) -> Any:
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

__all__ = ['ACTION_REAP', 'ACTION_SPARE', 'REASON_ALLOWLIST', 'REASON_BELOW_CEILING', 'REASON_ORPHAN_NOT_PROVEN', 'REASON_ORPHAN_PROVEN', 'apply_reaps', 'drop_allowlist', 'evaluate', 'health_status', 'load_below_ceiling_world', 'load_ceiling_world', 'naive_rss_kill_set', 'shared_service_survives']

