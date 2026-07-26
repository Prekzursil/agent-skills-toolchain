"""RETRY POLICY — pure, and deliberately almost empty.

Only ``win-arg-limit`` retries, and it retries EXACTLY once (route the prompt to a file/stdin
and try again). Everything else stops: a blind retry on a severed stream re-runs work that may
already have landed, and a blind retry on a policy violation just re-violates the policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentspec.taxonomy import is_reason

RETRYABLE_ONCE: tuple[str, ...] = ("win-arg-limit",)


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Whether to retry, which attempt number comes next, and WHY (for the journal)."""

    retry: bool
    next_attempt: int
    reason: str
    rationale: str


def plan_retry(reason: str, *, attempt: int) -> RetryDecision:
    """Decide whether ``reason`` on ``attempt`` earns one more try."""
    if attempt <= 0:
        raise ValueError("attempt must be >= 1")
    if not is_reason(reason):
        raise ValueError(f"reason {reason!r} is not in the closed taxonomy")
    if reason not in RETRYABLE_ONCE:
        return RetryDecision(
            retry=False,
            next_attempt=attempt,
            reason=reason,
            rationale=f"no automatic retry for {reason}",
        )
    if attempt >= 2:
        return RetryDecision(
            retry=False,
            next_attempt=attempt,
            reason=reason,
            rationale=f"already retried once for {reason}; stop",
        )
    return RetryDecision(
        retry=True,
        next_attempt=attempt + 1,
        reason=reason,
        rationale="retry once with the prompt routed to a file/stdin",
    )
