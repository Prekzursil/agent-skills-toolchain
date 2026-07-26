"""The ONE closed failure taxonomy every runtime, adapter and monitor matches on.

Members are deliberately *segment*-shaped so a parametrised code (``rail-exit-137``,
``timeout-1800s``, ``env-missing-XAI_API_KEY``) is recognisable by prefix WITHOUT
``str.startswith`` accepting a near-miss like ``rail-exiting``. The measured lesson behind
that care: a comparison regex of ``[<>=]{1,2}`` matched a bare ``=`` and read an initialiser
as a threshold, so the matcher must pin the boundary, not just the prefix.

``severed-stream`` is load-bearing and is NOT interchangeable with the fine-grained receipt
reasons: exit 0 with an unusable receipt is SEVERED. :mod:`agentspec.oracle` emits both — the
fine cause for the operator and ``severed-stream`` for consumers that match on the family.

**This is not the repo's only failure vocabulary.** ``hooks/_shared/failure_taxonomy.py`` has
its own set for the hook/barrier layer, using ``codex-exit-<n>`` where this uses
``rail-exit-<n>`` (vendor-neutral) and ``"429"`` where this uses ``rate-limited-<status>``. A
monitor matching one will NOT match the other, so the README carries the mapping table.
``rate-limited`` was added here after a reviewer measured that an adapter hitting a 429 could
not render a terminal marker or an envelope error code at all without editing this module.
"""

from __future__ import annotations

REASONS: tuple[str, ...] = (
    "budget-exhausted",
    "env-missing",
    "policy-violation",
    "progress-stream",
    "rail-exit",
    "rate-limited",
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


def family(code: str) -> str:
    """The taxonomy MEMBER behind a bare-or-parametrised ``code``; ``""`` when there is none.

    A parametrised code is ``<member>-<detail>``; the hyphen boundary is required, so
    ``rail-exiting`` resolves to ``""`` even though ``rail-exit`` is a member.

    This exists so a POLICY can branch on the member (``plan_retry`` must treat
    ``rate-limited-429`` exactly like ``rate-limited``) without re-implementing the boundary
    rule. One implementation, so a second copy cannot drift and accept a near-miss.
    """
    for member in REASONS:
        if code == member or code.startswith(member + "-"):
            return member
    return ""


def is_reason(code: str) -> bool:
    """True when ``code`` is a taxonomy member, bare or parametrised."""
    return bool(family(code))


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


def rate_limited(status: int) -> str:
    """Render the ``rate-limited-<status>`` reason for a 429/529-class refusal.

    The repo's pre-existing ``hooks/_shared/failure_taxonomy.py`` labels this class ``"429"``;
    this package keeps the segment shape (``rate-limited-429``) so ``family`` recognises it
    like every other member. The README carries the mapping between the two vocabularies.

    Only a 4xx/5xx status is accepted — ``rate-limited-200`` would be a reason nobody can act
    on, and minting an unusable code is how a closed taxonomy stops being closed in practice.
    """
    if not 400 <= status <= 599:
        return _refuse(f"rate_limited: {status} is not a 4xx/5xx status")
    return f"rate-limited-{status}"


def env_missing(name: str) -> str:
    """Render the ``env-missing-<NAME>`` reason. Never carries the variable's VALUE."""
    if not name:
        return _refuse("env_missing: name must be non-empty")
    return f"env-missing-{name}"


def _refuse(message: str) -> str:
    """Raise :class:`ValueError`; the ``-> str`` return type keeps callers total."""
    raise ValueError(message)
