"""The shared observation envelope (pure).

One envelope shape is used across every lane of this program:

    ``status`` (``success`` | ``warning`` | ``error``) . ``summary`` .
    ``next_actions`` . ``artifacts``

An ERROR envelope additionally carries a **root-cause hint**, a **safe retry
instruction** and an **explicit stop condition**. :func:`error` REFUSES to build one
without all three, because "error-only output without next steps" is a named
anti-pattern: it leaves the caller looping on an unrecoverable failure with nothing to
tell it when to stop.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcpctl.safety import strip_controls

__all__ = ["Envelope", "STATUSES", "error", "success", "terminal_line", "warning"]

STATUSES = ("success", "warning", "error")


@dataclass(frozen=True)
class Envelope:
    """A typed observation result. Every text field is control-stripped on build."""

    status: str
    summary: str
    next_actions: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    root_cause: str = ""
    retry: str = ""
    stop_condition: str = ""

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}, got {self.status!r}")
        object.__setattr__(self, "summary", strip_controls(self.summary))
        object.__setattr__(self, "root_cause", strip_controls(self.root_cause))
        object.__setattr__(self, "retry", strip_controls(self.retry))
        object.__setattr__(self, "stop_condition", strip_controls(self.stop_condition))
        object.__setattr__(
            self, "next_actions", tuple(strip_controls(a) for a in self.next_actions)
        )
        object.__setattr__(
            self, "artifacts", tuple(strip_controls(a) for a in self.artifacts)
        )

    def to_dict(self) -> dict[str, object]:
        """JSON-able form. The error-only triple is omitted on non-error envelopes."""
        payload: dict[str, object] = {
            "status": self.status,
            "summary": self.summary,
            "next_actions": list(self.next_actions),
            "artifacts": list(self.artifacts),
        }
        if self.status == "error":
            payload["root_cause"] = self.root_cause
            payload["retry"] = self.retry
            payload["stop_condition"] = self.stop_condition
        return payload


def success(
    summary: str,
    *,
    next_actions: tuple[str, ...] = (),
    artifacts: tuple[str, ...] = (),
) -> Envelope:
    """Build a ``success`` envelope."""
    return Envelope(
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
) -> Envelope:
    """Build a ``warning`` envelope -- the run produced a usable result with caveats."""
    return Envelope(
        status="warning",
        summary=summary,
        next_actions=next_actions,
        artifacts=artifacts,
    )


def error(
    summary: str,
    *,
    root_cause: str,
    retry: str,
    stop_condition: str,
    next_actions: tuple[str, ...] = (),
    artifacts: tuple[str, ...] = (),
) -> Envelope:
    """Build an ``error`` envelope, requiring all three recovery fields.

    ``next_actions`` defaults to the retry instruction so an error is never emitted
    with an empty action list.
    """
    missing = [
        name
        for name, value in (
            ("root_cause", root_cause),
            ("retry", retry),
            ("stop_condition", stop_condition),
        )
        if not value.strip()
    ]
    if missing:
        raise ValueError(
            "error envelope requires a non-blank "
            f"{', '.join(missing)} -- an error without a recovery path and an explicit "
            "stop condition is the named anti-pattern this constructor exists to block"
        )
    return Envelope(
        status="error",
        summary=summary,
        next_actions=next_actions or (retry,),
        artifacts=artifacts,
        root_cause=root_cause,
        retry=retry,
        stop_condition=stop_condition,
    )


def terminal_line(unit_id: str, env: Envelope) -> str:
    """Render the mandated terminal state: ``SUCCESS:<id> ...`` / ``FAILED:<id> ...``.

    A ``warning`` is a SUCCESS with its caveat visible in the line -- the run produced
    a usable result, so reporting it as a failure would train the reader to ignore
    real failures.
    """
    verb = "FAILED" if env.status == "error" else "SUCCESS"
    return f"{verb}:{unit_id} {env.summary}"
