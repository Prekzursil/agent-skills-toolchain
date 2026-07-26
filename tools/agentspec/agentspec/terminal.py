"""TERMINAL-STATE rendering: every unit result is ``SUCCESS:<id>`` or ``FAILED:<id> <reason>``.

Open-ended prose is the measured driver of repetitive-action loops, and a vague summary was how
a severed dispatch got reported as done. So the shape is enforced, not merely recommended:
``<id>`` may not contain whitespace (it would make the marker unparseable) and ``<reason>`` must
be a member of the closed taxonomy.

A SEVERED verdict renders ``FAILED:<id> severed-stream (<fine-reason>)`` — ``severed-stream``
comes FIRST so a consumer that greps for it matches, while the operator still sees the fine
cause.
"""

from __future__ import annotations

import re

from agentspec.taxonomy import is_reason

TERMINAL_RE = re.compile(r"^(?:SUCCESS:\S+|FAILED:\S+ [^\s].*)$")
"""Anchored at both ends: a line either IS a terminal marker or it is not."""


def success_line(unit_id: str) -> str:
    """Render ``SUCCESS:<id>``."""
    return f"SUCCESS:{_checked_id(unit_id)}"


def failure_line(unit_id: str, reason: str) -> str:
    """Render ``FAILED:<id> <reason>`` with ``reason`` checked against the taxonomy."""
    checked = _checked_id(unit_id)
    if not is_reason(reason):
        raise ValueError(f"reason {reason!r} is not in the closed taxonomy")
    return f"FAILED:{checked} {reason}"


def terminal_line(verdict: object) -> str:
    """Render any :class:`agentspec.oracle.Verdict` as its terminal marker.

    Typed as ``object`` on purpose: importing ``Verdict`` here would make
    :mod:`agentspec.oracle` and this module mutually dependent, and duck-typing keeps the
    renderer usable by a runtime that carries its own verdict record.
    """
    unit_id = str(getattr(verdict, "unit_id", ""))
    if getattr(verdict, "ok", False):
        return success_line(unit_id)
    reason = str(getattr(verdict, "reason", "") or "")
    if getattr(verdict, "severed", False):
        return f"{failure_line(unit_id, 'severed-stream')} ({reason})"
    return failure_line(unit_id, reason)


def _checked_id(unit_id: str) -> str:
    if not unit_id or any(ch.isspace() for ch in unit_id):
        raise ValueError(f"unit_id must be non-empty and whitespace-free, got {unit_id!r}")
    return unit_id
