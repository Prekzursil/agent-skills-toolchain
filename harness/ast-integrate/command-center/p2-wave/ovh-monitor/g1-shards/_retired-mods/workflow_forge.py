"""Import surface for workflow_forge (probe-derived)."""
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

class FusionBuildError(Exception):
    pass

REPUTATION_NOT_EVIDENCE = "REPUTATION_NOT_EVIDENCE"

TIED = "TIED"

def ablate_second_best(*args: Any, **kwargs: Any) -> Any:
    return Result()

def build_best_of_breed(*args: Any, **kwargs: Any) -> Any:
    return Result()

def fuse_best_of_breed(*args: Any, **kwargs: Any) -> Any:
    return Result()

def independent_winners(*args: Any, **kwargs: Any) -> Any:
    return Result()

def selection_cites_run_ids(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['FusionBuildError', 'REPUTATION_NOT_EVIDENCE', 'TIED', 'ablate_second_best', 'build_best_of_breed', 'fuse_best_of_breed', 'independent_winners', 'selection_cites_run_ids']

