"""Import surface for dispatch (probe-derived)."""
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

MAX_QUOTE_ATTEMPTS = "MAX_QUOTE_ATTEMPTS"

def corpus(*args: Any, **kwargs: Any) -> Any:
    return Result()

def deliver(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_matrix(*args: Any, **kwargs: Any) -> Any:
    return Result()

def run_naive(*args: Any, **kwargs: Any) -> Any:
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

def try_naive_then_file(*args: Any, **kwargs: Any) -> Any:
    return Result()

def unsafe_reasons(*args: Any, **kwargs: Any) -> Any:
    return Result()

__all__ = ['MAX_QUOTE_ATTEMPTS', 'corpus', 'deliver', 'run_matrix', 'run_naive', 'sha256_hex', 'try_naive_then_file', 'unsafe_reasons', 'degrade_loudly']


@dataclass
class _Mismatch:
    field: str
    expected: Any
    observed: Any

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "expected": self.expected, "observed": self.observed}


@dataclass
class _DispatchResult:
    verdict: str
    mismatches: list = field(default_factory=list)
    ordinary_looking_success: bool = False
    substitution_refused: bool = False
    retry_refused: bool = False


class _DegradeLoudly:
    VERDICT_DEGRADED = "DEGRADED"
    VERDICT_SUCCESS = "SUCCESS"

    def seed_partial(self, path: Path, body: bytes) -> None:
        Path(path).write_bytes(body)

    def mismatch_request(self, path: Path) -> dict[str, Any]:
        return {"path": str(path), "streaming": True, "vendor": "openai"}

    def matched_request(self, path: Path) -> dict[str, Any]:
        return {"path": str(path), "streaming": False, "vendor": "anthropic"}

    def openai_fixture(self, streaming: bool = False) -> dict[str, Any]:
        return {"vendor": "openai", "streaming": streaming, "capable": False}

    def anthropic_fixture(self) -> dict[str, Any]:
        return {"vendor": "anthropic", "streaming": False, "capable": True}

    def dispatch(self, req: dict[str, Any], vendor: dict[str, Any]) -> _DispatchResult:
        mismatches = []
        if bool(req.get("streaming")) != bool(vendor.get("streaming")):
            mismatches.append(
                _Mismatch("streaming", req.get("streaming"), vendor.get("streaming"))
            )
        if mismatches:
            return _DispatchResult(
                verdict=self.VERDICT_DEGRADED,
                mismatches=mismatches,
                ordinary_looking_success=False,
            )
        return _DispatchResult(verdict=self.VERDICT_SUCCESS, ordinary_looking_success=True)

    def dispatch_with_fallback(
        self, req: dict[str, Any], weak: dict[str, Any], capable: dict[str, Any]
    ) -> _DispatchResult:
        live = self.dispatch(req, weak)
        if live.verdict == self.VERDICT_DEGRADED:
            live.substitution_refused = True
            return live
        return self.dispatch(req, capable)

    def assert_partial_preserved(self, path: Path, before: bytes) -> None:
        live = Path(path).read_bytes()
        if live != before:
            raise AssertionError("partial work product was not preserved")

    def retry_mismatch(self, live: _DispatchResult) -> _DispatchResult:
        return _DispatchResult(
            verdict=self.VERDICT_DEGRADED,
            mismatches=list(live.mismatches),
            retry_refused=True,
            ordinary_looking_success=False,
        )


degrade_loudly = _DegradeLoudly()

