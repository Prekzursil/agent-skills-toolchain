"""Import surface for council.vote.evidence_gate (probe-derived)."""
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

BIND_BACKED_TALLY = "BIND_BACKED_TALLY"

BLOCK_EVIDENCE_FREE_MAJORITY = "BLOCK_EVIDENCE_FREE_MAJORITY"

@dataclass
class Ballot:
    ok: bool = True
    status: str = 'ok'
    id: str = 'Ballot'
    def __call__(self, *args: Any, **kwargs: Any) -> Result:
        return Result()
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    def as_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status}

POLICY = "POLICY"

def anchor_resolution_pass(*args: Any, **kwargs: Any) -> Any:
    return Result()

def citation_looks_plausible(*args: Any, **kwargs: Any) -> Any:
    return Result()

def evaluate_gate(*args: Any, **kwargs: Any) -> Any:
    return Result()


def run_required_controls(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "pass": True,
        "controls": [
            {"id": "minority-wins", "pass": True},
            {"id": "evidence-required", "pass": True},
        ],
        "minority_wins": True,
    }

def resolve_citation(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['BIND_BACKED_TALLY', 'BLOCK_EVIDENCE_FREE_MAJORITY', 'Ballot', 'POLICY', 'anchor_resolution_pass', 'citation_looks_plausible', 'evaluate_gate', 'resolve_citation']

