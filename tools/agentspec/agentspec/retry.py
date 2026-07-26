"""RETRY POLICY — pure, and deliberately almost empty.

Exactly two families retry, and both are BOUNDED:

* ``win-arg-limit`` retries EXACTLY once (route the prompt to a file/stdin and try again);
* ``rate-limited`` retries up to :data:`RATE_LIMIT_MAX_ATTEMPTS` total attempts with a
  deterministic doubling backoff.

Everything else stops. A blind retry on a severed stream re-runs work that may already have
landed, and a blind retry on a policy violation just re-violates the policy.

**"No automatic retry" is not "never re-dispatch".** For a severed stream the ORACLE tells the
operator to re-dispatch the same unit once (``oracle._retry_instruction``); the difference is
that a human or a runtime decides, having read the diagnostic tail, rather than this function
looping on its own. The repo's ``hooks/_shared/failure_taxonomy.py`` encodes the same split as
``action="redispatch", max_retries=1`` — the two agree; only the actor differs.

**JITTER IS DELIBERATELY ABSENT.** The hooks-side 429 policy says "exponential backoff with
jitter", but jitter needs entropy and :mod:`agentspec.determinism` fails this package's own
source on a ``random`` import. So agentspec supplies the deterministic SCHEDULE and the
transport shim adds jitter to it. That keeps every eval row byte-reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentspec.taxonomy import family

RETRYABLE_ONCE: tuple[str, ...] = ("win-arg-limit",)

RATE_LIMIT_MAX_ATTEMPTS = 6
"""Total attempts for a rate limit: 1 initial + 5 retries, mirroring the hooks-side
``HANDLERS["429"]`` policy (``action="backoff", max_retries=5``)."""

RATE_LIMIT_BASE_BACKOFF_MS = 1000
"""First wait, in ms. Doubles per attempt, so the full schedule is 1+2+4+8+16 = 31 s."""


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Whether to retry, which attempt number comes next, WHY, and how long to wait first.

    ``backoff_ms`` is 0 for every non-rate-limited decision, so a consumer may sleep it
    unconditionally. It is an ``int`` for the same wire-parity reason as ``RailResult.wall_ms``:
    an integral float renders ``1.0`` in Python and ``1`` in JS.
    """

    retry: bool
    next_attempt: int
    reason: str
    rationale: str
    backoff_ms: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.backoff_ms, bool) or not isinstance(self.backoff_ms, int):
            raise TypeError(
                f"backoff_ms must be an int, not {type(self.backoff_ms).__name__}"
            )
        if self.backoff_ms < 0:
            raise ValueError("backoff_ms must be >= 0")


def rate_limit_backoff_ms(attempt: int) -> int:
    """The wait before the retry that follows ``attempt``. Pure: no clock, no entropy."""
    if attempt <= 0:
        raise ValueError("attempt must be >= 1")
    return RATE_LIMIT_BASE_BACKOFF_MS * 2 ** (attempt - 1)


def plan_retry(reason: str, *, attempt: int) -> RetryDecision:
    """Decide whether ``reason`` on ``attempt`` earns another try.

    Matching is on the taxonomy MEMBER, so ``win-arg-limit-34472`` and ``rate-limited-429``
    get the same policy as their bare forms — a suffix must not silently disable a retry.
    """
    if attempt <= 0:
        raise ValueError("attempt must be >= 1")
    member = family(reason)
    if not member:
        raise ValueError(f"reason {reason!r} is not in the closed taxonomy")
    if member == "rate-limited":
        return _plan_rate_limited(reason, attempt)
    if member not in RETRYABLE_ONCE:
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


def _plan_rate_limited(reason: str, attempt: int) -> RetryDecision:
    """Bounded backoff. The EXPLICIT stop condition is the attempt ceiling, never a loop."""
    if attempt >= RATE_LIMIT_MAX_ATTEMPTS:
        return RetryDecision(
            retry=False,
            next_attempt=attempt,
            reason=reason,
            rationale=(
                f"rate-limited: all {RATE_LIMIT_MAX_ATTEMPTS} attempts spent; stop and "
                f"report FAILED"
            ),
        )
    wait_ms = rate_limit_backoff_ms(attempt)
    return RetryDecision(
        retry=True,
        next_attempt=attempt + 1,
        reason=reason,
        rationale=(
            f"rate-limited: back off {wait_ms} ms, then retry as attempt "
            f"{attempt + 1} of {RATE_LIMIT_MAX_ATTEMPTS}"
        ),
        backoff_ms=wait_ms,
    )
