"""Budget tracker + regime-based early stop for the deep-research harness.

Lens 12 find 3 (Budget Tracker / BATS, s1 budget forcing, Anthropic effort
rules). The loop carries one continuously updated ``Budget`` over three axes -
tool calls, an estimated token count and wall-clock seconds - and derives a
*regime* from the most-consumed ("binding") axis:

    explore   < 60 %  spend freely, metered tools allowed
    converge  60-85 % no metered tools; finish the open sub-questions
    finalize  > 85 %  "beast mode": no new searches, render NOW

``finalize`` renders with terminal status ``partial:budget`` (or
``partial:timeout`` when the wall clock is the binding axis) instead of
starting sub-question 7 and dying mid-fetch on a RAM-starved box.

Pure and offline: the clock is injected so tests never sleep. ``spend`` records
overspend honestly rather than raising - the loop may already be mid-call.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from .report import STATUS_PARTIAL_BUDGET, STATUS_PARTIAL_TIMEOUT

EXPLORE = "explore"
CONVERGE = "converge"
FINALIZE = "finalize"
REGIMES = (EXPLORE, CONVERGE, FINALIZE)

CONVERGE_AT = 0.60
FINALIZE_ABOVE = 0.85

# Effort classes -> default per-sub-question call allotments (Lens 12 find 8,
# after Anthropic's scaling rules: simple fact 3-10 calls, comparisons 10-15).
EFFORT_FACT = "fact"
EFFORT_COMPARE = "compare"
EFFORT_DEEP = "deep"
EFFORT_CALLS: dict[str, int] = {EFFORT_FACT: 3, EFFORT_COMPARE: 8, EFFORT_DEEP: 15}

_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Cheap deterministic token estimate (~4 chars/token; non-empty >= 1)."""
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


@dataclass(slots=True)
class Budget:
    """Mutable per-run budget over calls / tokens / wall-clock seconds."""

    max_calls: int
    max_seconds: float | None = None
    max_tokens: int | None = None
    used_calls: int = 0
    used_tokens: int = 0
    clock: Callable[[], float] = time.monotonic
    started: float | None = field(default=None)

    def __post_init__(self) -> None:
        if self.max_calls <= 0:
            raise ValueError("max_calls must be positive")
        if self.max_seconds is not None and self.max_seconds <= 0:
            raise ValueError("max_seconds must be positive when set")
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive when set")
        if self.started is None:
            self.started = self.clock()

    # --- spending ---------------------------------------------------------
    def spend(self, *, calls: int = 1, tokens: int = 0) -> None:
        """Record consumption. Never raises on overspend (see module doc)."""
        if calls < 0 or tokens < 0:
            raise ValueError("cannot spend a negative amount")
        self.used_calls += calls
        self.used_tokens += tokens

    # --- axes -------------------------------------------------------------
    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, self.clock() - (self.started or 0.0))

    @property
    def seconds_left(self) -> float | None:
        if self.max_seconds is None:
            return None
        return max(0.0, self.max_seconds - self.elapsed_seconds)

    @property
    def calls_left(self) -> int:
        return max(0, self.max_calls - self.used_calls)

    def _fractions(self) -> dict[str, float]:
        fractions = {"calls": self.used_calls / self.max_calls}
        if self.max_tokens is not None:
            fractions["tokens"] = self.used_tokens / self.max_tokens
        if self.max_seconds is not None:
            fractions["seconds"] = self.elapsed_seconds / self.max_seconds
        return fractions

    @property
    def binding_axis(self) -> str:
        """The most-consumed axis (``calls`` / ``tokens`` / ``seconds``)."""
        fractions = self._fractions()
        best = max(fractions.values())
        # Stable tie-break in insertion order: calls, then tokens, then seconds.
        return next(axis for axis, value in fractions.items() if value == best)

    @property
    def fraction_used(self) -> float:
        return max(self._fractions().values())

    @property
    def exhausted(self) -> bool:
        return self.fraction_used >= 1.0

    # --- regime -----------------------------------------------------------
    @property
    def regime(self) -> str:
        used = self.fraction_used
        if used < CONVERGE_AT:
            return EXPLORE
        if used <= FINALIZE_ABOVE:
            return CONVERGE
        return FINALIZE

    @property
    def allows_new_search(self) -> bool:
        """``finalize`` is beast mode: stop searching, render what exists."""
        return self.regime != FINALIZE

    @property
    def allows_metered(self) -> bool:
        """Metered tools (Perplexity deep research, agent runs) only in explore."""
        return self.regime == EXPLORE

    def can_afford(self, calls: int) -> bool:
        """True if an allotment of ``calls`` fits in what is left."""
        return calls <= self.calls_left

    @property
    def terminal_status(self) -> str | None:
        """Status to render with if the run stops now; ``None`` while searching."""
        if self.regime != FINALIZE:
            return None
        if self.binding_axis == "seconds":
            return STATUS_PARTIAL_TIMEOUT
        return STATUS_PARTIAL_BUDGET

    # --- the one-line loop prefix -----------------------------------------
    def status_line(self) -> str:
        """``Budget: 11/20 calls, 6 min left, regime=converge`` (prepend per loop)."""
        parts = [f"Budget: {self.used_calls}/{self.max_calls} calls"]
        if self.max_tokens is not None:
            parts.append(f"~{self.used_tokens}/{self.max_tokens} tokens")
        elif self.used_tokens:
            parts.append(f"~{self.used_tokens} tokens")
        if self.max_seconds is not None:
            minutes = int(round((self.seconds_left or 0.0) / 60))
            parts.append(f"{minutes} min left")
        parts.append(f"regime={self.regime}")
        return ", ".join(parts)
