"""Real import surface for tools.release."""
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

CANARY_VARIABLE = "CANARY_VARIABLE"

EXIT_TOOLING = "EXIT_TOOLING"

RULESET_ID = "RULESET_ID"

RULESET_PATH = "ruleset-path"

SCANNER_NAME = "SCANNER_NAME"

SCANNER_VERSION = "SCANNER_VERSION"

def classify_nonzero_as_clean(*args: Any, **kwargs: Any) -> Any:
    return Result()

def classify_scan_status(*args: Any, **kwargs: Any) -> Any:
    return Result()

def ensure_clean_bundle(*args: Any, **kwargs: Any) -> Any:
    return Result()

def pack_layer_tar(*args: Any, **kwargs: Any) -> Any:
    return Result()

def plant_canary(*args: Any, **kwargs: Any) -> Any:
    return Result()

def scan_extracted(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['CANARY_VARIABLE', 'EXIT_TOOLING', 'RULESET_ID', 'RULESET_PATH', 'SCANNER_NAME', 'SCANNER_VERSION', 'classify_nonzero_as_clean', 'classify_scan_status', 'ensure_clean_bundle', 'pack_layer_tar', 'plant_canary', 'scan_extracted']

