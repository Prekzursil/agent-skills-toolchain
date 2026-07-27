"""The shared OBSERVATION ENVELOPE — one data model across every lane.

Four mandatory fields on every adapter / work-unit result:
``status`` (``success|warning|error``) · ``summary`` · ``next_actions`` · ``artifacts``.

An ERROR path additionally carries a root-cause hint, a safe retry instruction and an
EXPLICIT stop condition. "error-only output without next steps" is a named anti-pattern, so
:func:`validate_observation` rejects an error envelope with an empty ``next_actions``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from agentspec import wire
from agentspec.taxonomy import is_reason

Status = Literal["success", "warning", "error"]

ENVELOPE_FIELDS: tuple[str, ...] = ("status", "summary", "next_actions", "artifacts")
"""The four mandated field names, in wire order."""

STATUSES: tuple[str, ...] = ("success", "warning", "error")


@dataclass(frozen=True, slots=True)
class ErrorDetail:
    """The three recovery affordances an error path MUST carry, plus its taxonomy code."""

    code: str
    root_cause: str
    retry_instruction: str
    stop_condition: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "root_cause": self.root_cause,
            "retry_instruction": self.retry_instruction,
            "stop_condition": self.stop_condition,
        }


@dataclass(frozen=True, slots=True)
class Observation:
    """One observation. Frozen: a result is a record, never a mutable accumulator."""

    status: str
    summary: str
    next_actions: tuple[str, ...]
    artifacts: tuple[str, ...]
    error: ErrorDetail | None = None

    def as_dict(self) -> dict[str, Any]:
        """The wire form: exactly the four fields, plus ``error`` only when present."""
        payload: dict[str, Any] = {
            "status": self.status,
            "summary": self.summary,
            "next_actions": list(self.next_actions),
            "artifacts": list(self.artifacts),
        }
        if self.error is not None:
            payload["error"] = self.error.as_dict()
        return payload


def success(
    summary: str,
    *,
    next_actions: tuple[str, ...] = (),
    artifacts: tuple[str, ...] = (),
) -> Observation:
    return Observation(
        status="success",
        summary=summary,
        next_actions=next_actions,
        artifacts=artifacts,
    )


def warning(
    summary: str,
    *,
    next_actions: tuple[str, ...] = (),
    artifacts: tuple[str, ...] = (),
) -> Observation:
    return Observation(
        status="warning",
        summary=summary,
        next_actions=next_actions,
        artifacts=artifacts,
    )


def error(
    summary: str,
    detail: ErrorDetail,
    *,
    next_actions: tuple[str, ...],
    artifacts: tuple[str, ...] = (),
) -> Observation:
    """Build an error envelope. ``next_actions`` is REQUIRED and must be non-empty."""
    if not next_actions:
        raise ValueError(
            "error(): next_actions must be non-empty (error-only output is banned)"
        )
    return Observation(
        status="error",
        summary=summary,
        next_actions=next_actions,
        artifacts=artifacts,
        error=detail,
    )


def validate_observation(obs: Observation) -> tuple[str, ...]:
    """Return the sorted violation ids for ``obs``; empty means valid."""
    violations: list[str] = []
    if obs.status not in STATUSES:
        violations.append("envelope-status-invalid")
    if wire.is_blank(obs.summary):
        violations.append("envelope-summary-empty")
    if obs.status == "error":
        violations.extend(_validate_error_path(obs))
    elif obs.error is not None:
        violations.append("envelope-error-unexpected")
    return wire.sorted_wire(violations)


def _validate_error_path(obs: Observation) -> list[str]:
    """Violations that only apply when ``status == "error"``."""
    if obs.error is None:
        return ["envelope-error-missing"]
    violations: list[str] = []
    if not obs.next_actions:
        violations.append("envelope-next-actions-empty")
    if not is_reason(obs.error.code):
        violations.append("envelope-error-code-unknown")
    if wire.is_blank(obs.error.root_cause):
        violations.append("envelope-error-root-cause-empty")
    if wire.is_blank(obs.error.retry_instruction):
        violations.append("envelope-error-retry-instruction-empty")
    if wire.is_blank(obs.error.stop_condition):
        violations.append("envelope-error-stop-condition-empty")
    return violations
