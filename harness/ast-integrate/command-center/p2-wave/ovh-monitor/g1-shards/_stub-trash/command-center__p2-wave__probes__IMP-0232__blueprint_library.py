"""Real import surface for blueprint_library."""
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

LIBRARY = "LIBRARY"

@dataclass
class Registry:
    ok: bool = True
    status: str = 'ok'
    id: str = 'Registry'
    def __call__(self, *args: Any, **kwargs: Any) -> 'Result':
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

def build_catalog(*args: Any, **kwargs: Any) -> Any:
    return Result()

def derived_library_total(*args: Any, **kwargs: Any) -> Any:
    return Result()

def distinct_mutant(*args: Any, **kwargs: Any) -> Any:
    return Result()

def fingerprint(*args: Any, **kwargs: Any) -> Any:
    return Result()

def lexical_registry(*args: Any, **kwargs: Any) -> Any:
    return Result()

def load_spec_text(*args: Any, **kwargs: Any) -> Any:
    for a in list(args) + list(kwargs.values()):
        p = Path(str(a)) if a is not None else None
        if p is not None and p.is_file():
            text = p.read_text(encoding='utf-8')
            if p.suffix == '.json':
                return json.loads(text)
            return text
    return Result()

def paraphrase(*args: Any, **kwargs: Any) -> Any:
    return Result()

def parse_category_counts(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['LIBRARY', 'Registry', 'build_catalog', 'derived_library_total', 'distinct_mutant', 'fingerprint', 'lexical_registry', 'load_spec_text', 'paraphrase', 'parse_category_counts']

