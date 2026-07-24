#!/usr/bin/env python3
"""failure_taxonomy.py -- C16: typed failure taxonomy -> per-class handler + retry + a
runtime-enforced two-strikes fingerprint pivot + a mandatory per-node timeout.

WHY THIS EXISTS (each rule paid for in a measured incident)
-----------------------------------------------------------
Three distinct measured problems, one mechanism (07-OPTIONS-C.md, C16):
  (a) A BLANKET retry wastes a whole budget re-running something that will never succeed.
      A `429` wants backoff; a `win-arg-limit` wants ``--ignore-user-config`` on the retry,
      NOT a plain re-run; a `schema-invalid` wants one re-ask then a stop.
  (b) ``parallel()`` has no per-agent timeout, so one hung agent deadlocks a whole phase.
      Every node therefore carries a mandatory ``timeout_s`` -- a missing one is a lint
      failure, not a silent default.
  (c) Repeated identical attempts on the same failing hypothesis (AGENTS.md 4b forbids it).
      After two consecutive failures on the SAME error fingerprint the runtime refuses a
      third identical attempt and escalates, emitting the fingerprint + the two attempts +
      a demand for a materially different approach.

The taxonomy classes are the ones the cross-vendor-dispatch rule already names, so a
producer and this handler cannot drift: severed-stream / codex-exit-<n> / win-arg-limit /
timeout-<n>s / schema-invalid, plus 429 (rate-limit) and an explicit UNCLASSIFIED so a
novel shape fails VISIBLY rather than falling through a default unnoticed.

Stdlib-only, no I/O; safe to import from a hook or the fan-out barrier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional

# -- taxonomy class labels (stable strings; a producer may compare against these) ----------
WIN_ARG_LIMIT = "win-arg-limit"
RATE_LIMITED = "429"
SCHEMA_INVALID = "schema-invalid"
SEVERED_STREAM = "severed-stream"
TIMEOUT = "timeout"
CODEX_EXIT = "codex-exit"  # rendered codex-exit-<n> by the caller when it has the code
UNCLASSIFIED = "unclassified"

# Ordered (most-specific first) stderr signatures. A timeout and a schema flag are decided
# BEFORE stderr because the runtime knows them authoritatively; these cover the rest.
_STDERR_SIGNATURES: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Windows CreateProcess 32767-char command-line cap (measured: os error 206 / payload_len).
    (
        WIN_ARG_LIMIT,
        re.compile(r"os error 206|payload_len=|command line is too long", re.I),
    ),
    # Anthropic/OpenAI rate limits and overloads.
    (
        RATE_LIMITED,
        re.compile(r"\b429\b|too many requests|rate.?limit|overloaded", re.I),
    ),
)


@dataclass(frozen=True)
class HandlerPolicy:
    """The per-class recovery policy. ``action`` is one of:
    retry | backoff | reask | redispatch | kill | fail."""

    failure_class: str
    action: str
    max_retries: int
    retry_mutation: Optional[str]  # a flag/change applied on the retry (win-arg-limit)
    terminal_on_exhaust: str  # "FAILED" | "UNKNOWN" once retries are spent
    backoff: bool  # exponential backoff with jitter (rate limit)


# The declared policy per class. Deliberately NOT "retry 3 times" for anything -- a blanket
# retry is the anti-pattern C16 removes.
HANDLERS: dict[str, HandlerPolicy] = {
    # retry ONCE, and only with --ignore-user-config (drops the MCP inventory that blew the arg cap).
    WIN_ARG_LIMIT: HandlerPolicy(
        WIN_ARG_LIMIT, "retry", 1, "--ignore-user-config", "FAILED", False
    ),
    # exponential backoff + jitter at a lowered arrival rate; several attempts are worthwhile.
    RATE_LIMITED: HandlerPolicy(RATE_LIMITED, "backoff", 5, None, "FAILED", True),
    # one re-ask with the schema restated, then fail (do not loop on a model that can't comply).
    SCHEMA_INVALID: HandlerPolicy(SCHEMA_INVALID, "reask", 1, None, "FAILED", False),
    # re-dispatch once; if the stream is still severed, UNKNOWN (not FAILED -- absence != failure).
    SEVERED_STREAM: HandlerPolicy(
        SEVERED_STREAM, "redispatch", 1, None, "UNKNOWN", False
    ),
    # kill and mark. Never hang; never blanket-retry a hang.
    TIMEOUT: HandlerPolicy(TIMEOUT, "kill", 0, None, "FAILED", False),
    # a nonzero codex exit: surface it, one re-dispatch is not obviously safe -> fail visibly.
    CODEX_EXIT: HandlerPolicy(CODEX_EXIT, "fail", 0, None, "FAILED", False),
    # a shape not in the taxonomy: fail VISIBLY (the spec's named failure mode is a silent fall-through).
    UNCLASSIFIED: HandlerPolicy(UNCLASSIFIED, "fail", 0, None, "FAILED", False),
}


def classify_failure(
    *,
    exit_code: Optional[int] = None,
    stderr: str = "",
    timed_out: bool = False,
    schema_valid: Optional[bool] = None,
    artifact_ok: Optional[bool] = None,
) -> str:
    """Classify a failure into the taxonomy. Precedence, highest first:

    1. ``timed_out``            -> TIMEOUT        (the runtime's own signal is authoritative)
    2. ``schema_valid is False``-> SCHEMA_INVALID (the caller validated the output shape)
    3. stderr signatures        -> WIN_ARG_LIMIT | RATE_LIMITED
    4. exit 0 + artifact_ok False-> SEVERED_STREAM (completion.py rule 2: exit-0-no-artifact)
    5. exit != 0 (and not 0/None)-> CODEX_EXIT
    6. otherwise                -> UNCLASSIFIED    (fail visibly, never a silent default)
    """
    if timed_out:
        return TIMEOUT
    if schema_valid is False:
        return SCHEMA_INVALID
    for label, pattern in _STDERR_SIGNATURES:
        if pattern.search(stderr or ""):
            return label
    if exit_code == 0 and artifact_ok is False:
        return SEVERED_STREAM
    if exit_code is not None and exit_code != 0:
        return CODEX_EXIT
    return UNCLASSIFIED


def handler_for(failure_class: str) -> HandlerPolicy:
    """The policy for a class. Raises KeyError for an unknown class -- a caller must classify
    into a known label first, so an unknown class is a programming error, never a silent default."""
    return HANDLERS[failure_class]


def require_timeout_s(node: Mapping[str, Any]) -> float:
    """C12 T0 lint: every node MUST declare a positive numeric ``timeout_s``. Returns the value
    on success; raises ValueError otherwise (a missing/zero/negative/non-numeric timeout is the
    unbounded-hang defect the spec makes unrepresentable)."""
    if "timeout_s" not in node:
        raise ValueError(
            f"node {node.get('id', '?')!r} has no timeout_s (mandatory per C16)"
        )
    value = node["timeout_s"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"node {node.get('id', '?')!r} timeout_s must be numeric, got {value!r}"
        )
    if value <= 0:
        raise ValueError(
            f"node {node.get('id', '?')!r} timeout_s must be > 0, got {value!r}"
        )
    return float(value)


class TwoStrikesBreaker:
    """Refuses a THIRD consecutive attempt on the same error fingerprint (AGENTS.md 4b).

    Per-fingerprint consecutive-failure counter: ``record_failure`` increments it,
    ``record_success`` clears it. ``refuses(fp)`` is True once the count reaches ``limit``
    (default 2), so the (limit+1)-th attempt on that fingerprint is refused. Distinct
    fingerprints are independent -- a genuinely different approach is never blocked by
    another's strikes."""

    def __init__(self, limit: int = 2):
        if limit < 1:
            raise ValueError("limit must be >= 1")
        self.limit = limit
        self._streak: dict[str, int] = {}

    def record_failure(self, fingerprint: str) -> int:
        self._streak[fingerprint] = self._streak.get(fingerprint, 0) + 1
        return self._streak[fingerprint]

    def record_success(self, fingerprint: str) -> None:
        self._streak.pop(fingerprint, None)

    def consecutive_failures(self, fingerprint: str) -> int:
        return self._streak.get(fingerprint, 0)

    def refuses(self, fingerprint: str) -> bool:
        return self._streak.get(fingerprint, 0) >= self.limit

    def escalation(self, fingerprint: str) -> dict[str, Any]:
        """The payload emitted when a third attempt is refused: the fingerprint, the strike
        count, and an explicit demand for a materially different approach (never a silent block)."""
        return {
            "fingerprint": fingerprint,
            "consecutive_failures": self._streak.get(fingerprint, 0),
            "demand": (
                "Two attempts on this exact error fingerprint have failed. A third identical "
                "attempt is refused (AGENTS.md 4b). Enumerate >=2 materially different "
                "alternative approaches, or escalate."
            ),
        }


if __name__ == "__main__":  # pragma: no cover - tiny self-check
    print(classify_failure(timed_out=True))
    print(classify_failure(exit_code=1, stderr="os error 206"))
    b = TwoStrikesBreaker()
    b.record_failure("x")
    b.record_failure("x")
    print("refuses 3rd:", b.refuses("x"))
