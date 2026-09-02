"""Retry wrappers under test: fault-injection, 429, zero-retry, silent retry."""
from __future__ import annotations

from typing import Any, Callable, TypeVar

T = TypeVar("T")


class DeterministicConnectError(Exception):
    """Always-the-same first-attempt failure. Not an environment condition."""


class HttpStatusError(Exception):
    def __init__(self, status: int, body: str, retry_after: str | None = None) -> None:
        self.status = status
        self.body = body
        self.retry_after = retry_after
        extra = f" Retry-After: {retry_after}" if retry_after else ""
        super().__init__(f"HTTP {status}: {body}{extra}")


class FailOnceService:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> dict[str, Any]:
        self.calls += 1
        if self.calls == 1:
            raise DeterministicConnectError(
                "ECONNRESET on first handshake (deterministic)"
            )
        return {"ok": True, "attempt": self.calls}


class RateLimitedThenOk:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> dict[str, Any]:
        self.calls += 1
        if self.calls == 1:
            raise HttpStatusError(429, "Too Many Requests", retry_after="2")
        return {"ok": True, "attempt": self.calls, "status": 200}


class AlwaysOk:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> dict[str, Any]:
        self.calls += 1
        return {"ok": True, "attempt": self.calls}


def retry_backoff(fn: Callable[[], T], max_attempts: int = 3) -> T:
    """Typical HTTP backoff wrapper: swallows attempt-1 errors, returns attempt-2 value."""
    last: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except BaseException as exc:
            last = exc
            if attempt >= max_attempts:
                raise
            continue
    assert last is not None
    raise last


def silent_retry(fn: Callable[[], T], max_attempts: int = 3) -> T:
    """Retry with zero telemetry — first-attempt error is discarded."""
    last: BaseException | None = None
    for _ in range(max_attempts):
        try:
            return fn()
        except BaseException as exc:
            last = exc
            continue
    raise RuntimeError(f"silent retry exhausted; last={last!r}")


def no_retry(fn: Callable[[], T]) -> T:
    """Zero-retry call site. Must not appear in the retry register."""
    return fn()
