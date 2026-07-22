"""Deterministic, opt-in fault injection for CRCP lifecycle boundaries.

The injector is disabled unless hook names are explicitly enabled.  Each
reached hook and each caller-recorded lifecycle step can be written to an
append-only JSONL trace.  Trace context is metadata-only and redacts keys that
look like credentials.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


FAIL_AFTER_INGEST = "fail_after_ingest"
FAIL_AFTER_SEND = "fail_after_send"
FAIL_AFTER_CLAIM = "fail_after_claim"
FAULT_HOOKS = frozenset(
    {
        FAIL_AFTER_INGEST,
        FAIL_AFTER_SEND,
        FAIL_AFTER_CLAIM,
    }
)

_SENSITIVE_MARKERS = (
    "authorization",
    "bearer",
    "credential",
    "jwt",
    "password",
    "proof",
    "secret",
    "token",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class InjectedFault(RuntimeError):
    """Raised at an enabled CRCP fault boundary."""

    def __init__(self, hook: str, occurrence: int, journey_id: str):
        self.hook = hook
        self.occurrence = occurrence
        self.journey_id = journey_id
        super().__init__(f"injected fault at {hook} occurrence {occurrence}")


class FaultInjector:
    """Record lifecycle steps and deterministically fail selected hooks.

    ``enabled_hooks`` is empty by default, making the object safe to wire into
    normal code paths.  For an enabled hook, ``failure_rate`` is applied to a
    SHA-256 value derived from seed, hook, and occurrence.  This avoids global
    PRNG state and produces the same decision regardless of thread scheduling.

    A hook fails at most ``max_failures_per_hook`` times per injector instance.
    Replay code should construct a disabled injector (or one with a different
    fault plan) while retaining the same trace path.
    """

    def __init__(
        self,
        *,
        seed: int | str = 0,
        enabled_hooks: Iterable[str] = (),
        failure_rate: float = 1.0,
        max_failures_per_hook: int = 1,
        trace_path: Path | None = None,
    ):
        hooks = frozenset(enabled_hooks)
        unknown = hooks - FAULT_HOOKS
        if unknown:
            raise ValueError(f"unknown fault hooks: {sorted(unknown)!r}")
        if not 0.0 <= failure_rate <= 1.0:
            raise ValueError("failure_rate must be between 0.0 and 1.0")
        if max_failures_per_hook < 0:
            raise ValueError("max_failures_per_hook must be non-negative")

        self.seed = str(seed)
        self.enabled_hooks = hooks
        self.failure_rate = float(failure_rate)
        self.max_failures_per_hook = int(max_failures_per_hook)
        self.trace_path = Path(trace_path) if trace_path is not None else None
        self.journey_id = hashlib.sha256(
            f"crcp-fault-journey\0{self.seed}".encode("utf-8")
        ).hexdigest()[:16]
        self._lock = threading.RLock()
        self._occurrences = {name: 0 for name in FAULT_HOOKS}
        self._failures = {name: 0 for name in FAULT_HOOKS}
        self._sequence = self._read_last_sequence()
        self._records: list[dict[str, Any]] = []

    @property
    def records(self) -> tuple[dict[str, Any], ...]:
        """Return an immutable snapshot of records made by this instance."""
        with self._lock:
            return tuple(dict(item) for item in self._records)

    def record_step(self, step: str, **context: Any) -> dict[str, Any]:
        """Record a non-failing journey step."""
        if not step or not isinstance(step, str):
            raise ValueError("step must be a non-empty string")
        return self._record("step", step, context=context)

    def fail_after_ingest(self, **context: Any) -> bool:
        return self._hook(FAIL_AFTER_INGEST, context)

    def fail_after_send(self, **context: Any) -> bool:
        return self._hook(FAIL_AFTER_SEND, context)

    def fail_after_claim(self, **context: Any) -> bool:
        return self._hook(FAIL_AFTER_CLAIM, context)

    def _hook(self, hook: str, context: dict[str, Any]) -> bool:
        with self._lock:
            self._occurrences[hook] += 1
            occurrence = self._occurrences[hook]
            should_fail = (
                hook in self.enabled_hooks
                and self._failures[hook] < self.max_failures_per_hook
                and self._decision(hook, occurrence)
            )
            self._record(
                "hook",
                hook,
                context=context,
                occurrence=occurrence,
                outcome="inject" if should_fail else "continue",
            )
            if should_fail:
                self._failures[hook] += 1
                raise InjectedFault(hook, occurrence, self.journey_id)
            return False

    def _decision(self, hook: str, occurrence: int) -> bool:
        if self.failure_rate <= 0.0:
            return False
        if self.failure_rate >= 1.0:
            return True
        raw = hashlib.sha256(
            f"{self.seed}\0{hook}\0{occurrence}".encode("utf-8")
        ).digest()[:8]
        sample = int.from_bytes(raw, "big") / float(1 << 64)
        return sample < self.failure_rate

    def _read_last_sequence(self) -> int:
        if self.trace_path is None or not self.trace_path.is_file():
            return 0
        last = 0
        try:
            with self.trace_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        value = json.loads(line)
                        last = max(last, int(value.get("sequence") or 0))
                    except (json.JSONDecodeError, TypeError, ValueError):
                        # A hard crash may leave a partial final line.
                        continue
        except OSError:
            return 0
        return last

    def _record(
        self,
        kind: str,
        name: str,
        *,
        context: dict[str, Any],
        occurrence: int | None = None,
        outcome: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._sequence += 1
            record: dict[str, Any] = {
                "schema": "crcp.fault_trace.v1",
                "sequence": self._sequence,
                "at": utc_now(),
                "journey_id": self.journey_id,
                "kind": kind,
                "name": name,
                "context": _safe_context(context),
            }
            if occurrence is not None:
                record["occurrence"] = occurrence
            if outcome is not None:
                record["outcome"] = outcome
            self._records.append(record)
            if self.trace_path is not None:
                self._append_trace(record)
            return dict(record)

    def _append_trace(self, record: dict[str, Any]) -> None:
        assert self.trace_path is not None
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        with self.trace_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())


def _safe_context(context: dict[str, Any], *, depth: int = 0) -> dict[str, Any]:
    """Return bounded metadata with credential-looking fields redacted."""
    safe: dict[str, Any] = {}
    for raw_key, value in context.items():
        key = str(raw_key)[:80]
        lowered = key.lower()
        if any(marker in lowered for marker in _SENSITIVE_MARKERS):
            safe[key] = "[REDACTED]"
            continue
        safe[key] = _safe_value(value, depth=depth)
    return safe


def _safe_value(value: Any, *, depth: int) -> Any:
    if depth >= 3:
        return "[TRUNCATED]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= 240 else value[:237] + "..."
    if isinstance(value, Path):
        return str(value)[:240]
    if isinstance(value, (list, tuple)):
        return [_safe_value(item, depth=depth + 1) for item in value[:20]]
    if isinstance(value, dict):
        return _safe_context(
            {str(k): v for k, v in list(value.items())[:20]},
            depth=depth + 1,
        )
    return f"<{type(value).__name__}>"


__all__ = [
    "FAIL_AFTER_CLAIM",
    "FAIL_AFTER_INGEST",
    "FAIL_AFTER_SEND",
    "FAULT_HOOKS",
    "FaultInjector",
    "InjectedFault",
]
