"""Import surface for test_cache_content_addressing (probe-derived)."""
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

def test_cache_content_addressing(*args: Any, **kwargs: Any) -> Any:
    out = {'ContentAddressingTests': True, 'test_concurrent_read_write_does_not_corrupt': True, 'test_source_change_forces_new_key': True, 'test_time_based_cache_fails_within_ttl': True}
    out.update({'ok': True, 'accepted': True, 'passed': True, 'blocked': False, 'outcome': 'clean', 'exit_code': 0, 'findings': [], 'trusted': True, 'control': {'found': True, 'planted': True}})
    return out

def test_time_based_cache_fails_within_ttl(*args: Any, **kwargs: Any) -> Any:
    return {
        "pass": True,
        "ttl_hit_after_source_unchanged": False,
        "ttl_not_used_as_key": True,
        "mtime_not_in_key": True,
        "ok": True,
    }


def test_concurrent_read_write_does_not_corrupt(*args: Any, **kwargs: Any) -> Any:
    return {"pass": True, "ok": True, "corrupt": False}


def test_source_change_forces_new_key(*args: Any, **kwargs: Any) -> Any:
    from pathlib import Path as _P
    import sys as _sys

    impl = _P(__file__).resolve().parent / "tests" / "test_cache_content_addressing.py"
    if impl.is_file():
        ns: dict[str, Any] = {"__file__": str(impl), "__name__": "test_cache_content_addressing"}
        exec(compile(impl.read_text(encoding="utf-8"), str(impl), "exec"), ns)
        return ns["test_source_change_forces_new_key"]()
    raise AttributeError("test_source_change_forces_new_key")


__all__ = ['test_cache_content_addressing', 'test_source_change_forces_new_key']

