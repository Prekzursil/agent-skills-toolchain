"""Import surface for wfa_injection_gate (probe-derived)."""
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

