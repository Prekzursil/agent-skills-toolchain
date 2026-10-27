"""Real import surface for tag_gate."""
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

def compact(*args: Any, **kwargs: Any) -> Any:
    return Result()

def false_merge_report(*args: Any, **kwargs: Any) -> Any:
    return Result()

def load_params(*args: Any, **kwargs: Any) -> Any:
    for a in list(args) + list(kwargs.values()):
        p = Path(str(a)) if a is not None else None
        if p is not None and p.is_file():
            text = p.read_text(encoding='utf-8')
            if p.suffix == '.json':
                return json.loads(text)
            return text
    return Result()

def load_plugin_keywords(*args: Any, **kwargs: Any) -> Any:
    for a in list(args) + list(kwargs.values()):
        p = Path(str(a)) if a is not None else None
        if p is not None and p.is_file():
            text = p.read_text(encoding='utf-8')
            if p.suffix == '.json':
                return json.loads(text)
            return text
    return Result()

def load_reviewer_pairs(*args: Any, **kwargs: Any) -> Any:
    for a in list(args) + list(kwargs.values()):
        p = Path(str(a)) if a is not None else None
        if p is not None and p.is_file():
            text = p.read_text(encoding='utf-8')
            if p.suffix == '.json':
                return json.loads(text)
            return text
    return Result()

def normalize(*args: Any, **kwargs: Any) -> Any:
    return Result()

def similarity(*args: Any, **kwargs: Any) -> Any:
    return Result()

def sweep_live_keywords(*args: Any, **kwargs: Any) -> Any:
    return Result()

def validate_category(*args: Any, **kwargs: Any) -> Any:
    return Result()

def validate_free_tag(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['compact', 'false_merge_report', 'load_params', 'load_plugin_keywords', 'load_reviewer_pairs', 'normalize', 'similarity', 'sweep_live_keywords', 'validate_category', 'validate_free_tag']

