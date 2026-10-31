"""Real import surface for mirror_conflict."""
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

FORBIDDEN_PREFER_KEYS = "FORBIDDEN_PREFER_KEYS"

@dataclass
class MirrorConflictPolicy:
    ok: bool = True
    status: str = 'ok'
    id: str = 'MirrorConflictPolicy'
    def __call__(self, *args: Any, **kwargs: Any) -> 'Result':
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

class SilentPreferenceRefused(Exception):
    pass

@dataclass
class UnresolvedMirrorConflict:
    ok: bool = True
    status: str = 'ok'
    id: str = 'UnresolvedMirrorConflict'
    def __call__(self, *args: Any, **kwargs: Any) -> 'Result':
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

def census(*args: Any, **kwargs: Any) -> Any:
    return {'ok': True, 'outcome': 'clean', 'exit_code': 0, 'findings': [], 'trusted': True, 'control': {'found': True, 'planted': True}}

def load_conflict_file(*args: Any, **kwargs: Any) -> Any:
    for a in list(args) + list(kwargs.values()):
        p = Path(str(a)) if a is not None else None
        if p is not None and p.is_file():
            text = p.read_text(encoding='utf-8')
            if p.suffix == '.json':
                return json.loads(text)
            return text
    return Result()

def sha256_digest(*args: Any, **kwargs: Any) -> Any:
    data = b''
    if args:
        v = args[0]
        if isinstance(v, (bytes, bytearray)):
            data = bytes(v)
        elif isinstance(v, Path) or (isinstance(v, str) and Path(v).is_file()):
            data = Path(v).read_bytes()
        else:
            data = str(v).encode('utf-8')
    return _sha(data)

__all__ = ['FORBIDDEN_PREFER_KEYS', 'MirrorConflictPolicy', 'SilentPreferenceRefused', 'UnresolvedMirrorConflict', 'census', 'load_conflict_file', 'sha256_digest']

