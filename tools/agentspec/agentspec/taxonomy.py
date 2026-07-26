"""The ONE closed failure taxonomy every runtime, adapter and monitor matches on.

Members are deliberately *segment*-shaped so a parametrised code (``rail-exit-137``,
``timeout-1800s``, ``env-missing-XAI_API_KEY``) is recognisable by prefix WITHOUT
``str.startswith`` accepting a near-miss like ``rail-exiting``. The measured lesson behind
that care: a comparison regex of ``[<>=]{1,2}`` matched a bare ``=`` and read an initialiser
as a threshold, so the matcher must pin the boundary, not just the prefix.

``severed-stream`` is load-bearing and is NOT interchangeable with the fine-grained receipt
reasons: exit 0 with an unusable receipt is SEVERED. :mod:`agentspec.oracle` emits both — the
fine cause for the operator and ``severed-stream`` for consumers that match on the family.
"""

from __future__ import annotations

REASONS: tuple[str, ...] = (
    "budget-exhausted",
    "env-missing",
    "policy-violation",
    "progress-stream",
    "rail-exit",
    "receipt-empty",
    "receipt-incomplete",
    "receipt-missing",
    "receipt-unparseable",
    "schema-invalid",
    "severed-stream",
    "spawn-failed",
    "timeout",
    "win-arg-limit",
)
"""Sorted, unique and CLOSED. Growing it is a reviewed diff, never an ad-hoc string."""


def is_reason(code: str) -> bool:
    """True when ``code`` is a taxonomy member, bare or parametrised.

    A parametrised code is ``<member>-<detail>``; the hyphen boundary is required, so
    ``rail-exiting`` is rejected even though ``rail-exit`` is a member.
    """
    if not code:
        return False
    for member in REASONS:
        if code == member or code.startswith(member + "-"):
            return True
    return False


def rail_exit(exit_code: int) -> str:
    """Render the ``rail-exit-<n>`` reason for a NON-ZERO rail exit."""
    if exit_code == 0:
        return _refuse("rail_exit: exit 0 is never a rail failure (SEVERED or SUCCESS)")
    return f"rail-exit-{exit_code}"


def timeout(seconds: int) -> str:
    """Render the ``timeout-<n>s`` reason. A dispatch has no implicit timeout."""
    if seconds <= 0:
        return _refuse(
            "timeout: seconds must be positive (an explicit budget is mandatory)"
        )
    return f"timeout-{seconds}s"


def env_missing(name: str) -> str:
    """Render the ``env-missing-<NAME>`` reason. Never carries the variable's VALUE."""
    if not name:
        return _refuse("env_missing: name must be non-empty")
    return f"env-missing-{name}"


def _refuse(message: str) -> str:
    """Raise :class:`ValueError`; the ``-> str`` return type keeps callers total."""
    raise ValueError(message)
