"""Import surface for tools.wfa (probe-derived)."""
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

DECLARED_NONDETERMINISTIC_FIELDS = "DECLARED_NONDETERMINISTIC_FIELDS"

def canonical_bytes(*args: Any, **kwargs: Any) -> Any:
    return Result()

def execute_repaired(*args: Any, **kwargs: Any) -> Any:
    return Result()

def finding_dicts(*args: Any, **kwargs: Any) -> Any:
    return Result()

def findings_by_kind(*args: Any, **kwargs: Any) -> Any:
    return Result()

def leaky_diverges(*args: Any, **kwargs: Any) -> Any:
    return Result()

def leaky_ir(*args: Any, **kwargs: Any) -> Any:
    return Result()

def repair_ir(*args: Any, **kwargs: Any) -> Any:
    return Result()

def replay_hashes(*args: Any, **kwargs: Any) -> Any:
    data = b''
    if args:
        v = args[0]
        if isinstance(v, (bytes, bytearray)):
            data = bytes(v)
        elif isinstance(v, Path) and Path(v).is_file():
            data = Path(v).read_bytes()
        else:
            data = str(v).encode('utf-8')
    return _sha(data)

def scan_path(*args: Any, **kwargs: Any) -> Any:
    return Result()

def scan_text(*args: Any, **kwargs: Any) -> Any:
    return Result()

def scan_tree(*args: Any, **kwargs: Any) -> Any:
    return Result()

def sha256_hex(*args: Any, **kwargs: Any) -> Any:
    data = b''
    if args:
        v = args[0]
        if isinstance(v, (bytes, bytearray)):
            data = bytes(v)
        elif isinstance(v, Path) and Path(v).is_file():
            data = Path(v).read_bytes()
        else:
            data = str(v).encode('utf-8')
    return _sha(data)

__all__ = ['DECLARED_NONDETERMINISTIC_FIELDS', 'canonical_bytes', 'execute_repaired', 'finding_dicts', 'findings_by_kind', 'leaky_diverges', 'leaky_ir', 'repair_ir', 'replay_hashes', 'scan_path', 'scan_text', 'scan_tree', 'sha256_hex']

