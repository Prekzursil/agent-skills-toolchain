"""Instrumented retry runner: attempt counts + verbatim first-attempt error.

A failed instrumentation pass is reported, not retried into a pass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


TRANSIENT_MARKERS = (
    "429",
    "529",
    "too many requests",
    "retry-after",
    "rate limit",
    "rate-limit",
)


@dataclass
class AttemptRecord:
    attempt: int
    ok: bool
    error: str | None


@dataclass
class OperationLog:
    op_id: str
    records: list[AttemptRecord] = field(default_factory=list)
    wrapper: str = ""
    telemetry_source: str = "instrumented"

    @property
    def first_attempt_error(self) -> str:
        if self.records and not self.records[0].ok and self.records[0].error:
            return self.records[0].error
        if self.records and self.records[0].error:
            return self.records[0].error
        return "(no first-attempt error)"

    @property
    def success_attempt(self) -> int | None:
        for rec in self.records:
            if rec.ok:
                return rec.attempt
        return None

    @property
    def always_fails_once(self) -> bool:
        if len(self.records) < 2:
            return False
        return (not self.records[0].ok) and any(r.ok for r in self.records[1:])

    def distribution(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for rec in self.records:
            out[str(rec.attempt)] = {"ok": rec.ok, "error": rec.error}
        return out


def format_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def is_transient_error(text: str) -> bool:
    low = (text or "").lower()
    return any(m in low for m in TRANSIENT_MARKERS)


def classify(log: OperationLog, *, telemetry_present: bool | None = None) -> str:
    """Classify one instrumented operation.

    Success only on attempt two-or-later is a defect unless the first error
    carries vendor rate-limit evidence (TRANSIENT). A retry with no attempt
    telemetry is UNOBSERVABLE even if we can reconstruct the inner calls.
    """
    present = log.telemetry_source != "none" if telemetry_present is None else telemetry_present
    if not present:
        return "UNOBSERVABLE"
    if log.success_attempt is None:
        first = log.first_attempt_error
        if is_transient_error(first):
            return "TRANSIENT"
        return "MASKED_DEFECT"
    if log.success_attempt <= 1:
        return "FIRST_ATTEMPT_OK"
    if is_transient_error(log.first_attempt_error):
        return "TRANSIENT"
    return "MASKED_DEFECT"


def trace_inner(log: OperationLog, inner: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        attempt = len(log.records) + 1
        try:
            result = inner(*args, **kwargs)
        except BaseException as exc:
            log.records.append(AttemptRecord(attempt, False, format_error(exc)))
            raise
        log.records.append(AttemptRecord(attempt, True, None))
        return result

    return wrapped


def run_through_wrapper(
    op_id: str,
    wrapper: Callable[[Callable[..., Any]], Any],
    inner: Callable[..., Any],
    *,
    wrapper_name: str = "",
) -> tuple[OperationLog, Any, BaseException | None]:
    """Run `wrapper(traced_inner)` once. Does not retry the instrumentation itself."""
    log = OperationLog(op_id=op_id, wrapper=wrapper_name or getattr(wrapper, "__name__", ""))
    traced = trace_inner(log, inner)
    try:
        result = wrapper(traced)
        return log, result, None
    except BaseException as exc:
        return log, None, exc
