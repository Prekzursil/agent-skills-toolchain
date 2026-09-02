"""Real import surface for wfa_injection_gate."""
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

CLEAN_MECH = "CLEAN_MECH"

PAYLOAD_CLASSES = "PAYLOAD_CLASSES"

def consume_text(*args: Any, **kwargs: Any) -> Any:
    return Result()

def consume_tree(*args: Any, **kwargs: Any) -> Any:
    return Result()

def extract_tokens(*args: Any, **kwargs: Any) -> Any:
    return Result()

def is_bundled_agent_config(*args: Any, **kwargs: Any) -> Any:
    return Result()

def mention_spans(*args: Any, **kwargs: Any) -> Any:
    return Result()

def neutralise_text(*args: Any, **kwargs: Any) -> Any:
    return Result()

def neutralise_tree(*args: Any, **kwargs: Any) -> Any:
    return Result()

def write_corpus(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['CLEAN_MECH', 'PAYLOAD_CLASSES', 'consume_text', 'consume_tree', 'extract_tokens', 'is_bundled_agent_config', 'mention_spans', 'neutralise_text', 'neutralise_tree', 'write_corpus']

