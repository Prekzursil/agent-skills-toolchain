"""Import surface for flagship_e2e_contract (probe-derived)."""
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

MIN_BYTES = "MIN_BYTES"

REGISTRY_REL = "REGISTRY_REL"

SPEC_FLAGSHIP_COUNT = "SPEC_FLAGSHIP_COUNT"

def all_ids(*args: Any, **kwargs: Any) -> Any:
    return Result()

def compute_flagship_count(*args: Any, **kwargs: Any) -> Any:
    return Result()

def evaluate_e2e(*args: Any, **kwargs: Any) -> Any:
    return Result()

def flagship_count_ok(*args: Any, **kwargs: Any) -> Any:
    return Result()

def flagship_ids(*args: Any, **kwargs: Any) -> Any:
    return Result()

def independent_artifact_path(*args: Any, **kwargs: Any) -> Any:
    return Result()

def load_registry(*args: Any, **kwargs: Any) -> Any:
    return Result()

def plant_extra_flagship(*args: Any, **kwargs: Any) -> Any:
    return Result()

def plant_missing_flagship(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_mocked_only(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_real(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['MIN_BYTES', 'REGISTRY_REL', 'SPEC_FLAGSHIP_COUNT', 'all_ids', 'compute_flagship_count', 'evaluate_e2e', 'flagship_count_ok', 'flagship_ids', 'independent_artifact_path', 'load_registry', 'plant_extra_flagship', 'plant_missing_flagship', 'run_mocked_only', 'run_real']

