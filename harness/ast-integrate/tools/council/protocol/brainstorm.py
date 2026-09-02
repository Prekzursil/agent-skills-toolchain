"""Import surface for council.protocol.brainstorm (probe-derived)."""
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

@dataclass
class IdeaLedger:
    ok: bool = True
    status: str = 'ok'
    id: str = 'IdeaLedger'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

@dataclass
class KernelBypass:
    ok: bool = True
    status: str = 'ok'
    id: str = 'KernelBypass'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

class LedgerMutationError(Exception):
    pass

class LedgerTamperError(Exception):
    pass

PROTOCOL_ID = "PROTOCOL_ID"

@dataclass
class RecordingKernel:
    ok: bool = True
    status: str = 'ok'
    id: str = 'RecordingKernel'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

UNIQUE_IDEA_TARGET = "UNIQUE_IDEA_TARGET"

def canonicalize_mechanism(*args: Any, **kwargs: Any) -> Any:
    return Result()

def pairwise_grouping_score(*args: Any, **kwargs: Any) -> Any:
    return Result()

def string_key(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['IdeaLedger', 'KernelBypass', 'LedgerMutationError', 'LedgerTamperError', 'PROTOCOL_ID', 'RecordingKernel', 'UNIQUE_IDEA_TARGET', 'canonicalize_mechanism', 'pairwise_grouping_score', 'string_key']

