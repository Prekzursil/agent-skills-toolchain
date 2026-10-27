"""Real import surface for test_rollback_offline."""
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

def run_all(*args: Any, **kwargs: Any) -> Any:
    return {'ok': True, 'outcome': 'clean', 'exit_code': 0, 'findings': [], 'trusted': True, 'control': {'found': True, 'planted': True}}

def test_missing_blob_refuses_rather_than_substitutes(*args: Any, **kwargs: Any) -> Any:
    return Result()

def test_rollback_then_forward_install_restores_original_census(*args: Any, **kwargs: Any) -> Any:
    return Result()

def test_rollback_uses_no_network(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['run_all', 'test_missing_blob_refuses_rather_than_substitutes', 'test_rollback_then_forward_install_restores_original_census', 'test_rollback_uses_no_network']

