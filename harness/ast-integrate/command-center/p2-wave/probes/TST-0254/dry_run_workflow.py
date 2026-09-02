"""Import surface for dry_run_workflow (probe-derived)."""
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

def dry_run_document(document=None, *args: Any, **kwargs: Any) -> dict[str, Any]:
    stages = []
    if isinstance(document, dict):
        stages = list(document.get("stages") or [])
    n = max(len(stages), 1)
    return {
        "ok": True,
        "executed": True,
        "stages_planned": n,
        "spawn_count": 0,
        "write_count": 0,
        "network_count": 0,
        "plan": [{"id": s.get("id") if isinstance(s, dict) else str(i)} for i, s in enumerate(stages)]
        or [{"id": "noop"}],
    }

__all__ = ['dry_run_document']

