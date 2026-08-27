"""``stall`` — the two-signal stall/blocked classifier + the corroboration table (WU6).

The board must distinguish three easily-confused conditions and colour them HONESTLY:

* **aborted** — a FACT (the source reported a failed / aborted end). Red.
* **stalled** — an INFERENCE that a unit is frozen. Stall detection from a single signal
  is unreliable (a stalled process and a long-finished one are indistinguishable from one
  reading), so a stall here requires TWO mechanically-independent signals that AGREE: the
  source FILE's mtime has not advanced (a filesystem signal) AND the parsed-content
  fingerprint has not changed across ``>= 2`` polls (a content signal). Amber, NEVER red —
  an inference must not masquerade as a fact.
* **blocked** — reachable but WAITING (e.g. an in-flight command that is not progressing
  while the file is NOT stale). Distinct from a stall: it is not frozen, it is paused.
  Amber, never red.

:data:`CORROBORATION` is the single-source-of-truth policy table (one row per
:class:`Condition`: its ``kind`` fact/inference, its ``severity``, and whether it needs
``>= 2`` signals before it may show). :func:`should_render_red` reads it, so the cardinal
"red only for a corroborated fact, never on one signal" guarantee is enforced in ONE place.

The classifier is a PURE function over injected signals; :class:`StallTracker` is the tiny
deterministic cross-poll counter that produces the content-freeze signal (no clock, no I/O)
— so the whole module reaches 100% line+branch under injected inputs and vendors cleanly
into a skill's plain Python.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "CORROBORATION",
    "Condition",
    "Corroboration",
    "StallSignals",
    "StallTracker",
    "classify_condition",
    "corroboration_for",
    "is_corroborated_stall",
    "should_render_red",
]

# a stall inference needs a content-freeze across at least this many consecutive polls.
_MIN_FREEZE_POLLS = 2


class Condition(StrEnum):
    """The corroborated per-unit condition the board colours (a ``str`` at runtime)."""

    ACTIVE = "active"
    IDLE = "idle"
    BLOCKED = "blocked"
    STALLED = "stalled"
    ABORTED = "aborted"


@dataclass(frozen=True)
class StallSignals:
    """The two mechanically-independent freeze signals a stall inference needs.

    ``mtime_stale`` — the source FILE's mtime has not advanced past the dead-man window
    (a filesystem signal). ``frozen_polls`` — the number of consecutive polls whose parsed
    content fingerprint did not change (a content signal, from :class:`StallTracker`). A
    stall is inferred only when BOTH agree; either one alone is a measurement artifact.
    """

    mtime_stale: bool
    frozen_polls: int


@dataclass(frozen=True)
class Corroboration:
    """One row of the corroboration policy: how a condition may be shown.

    ``kind`` ∈ {'fact', 'inference'}; ``severity`` ∈ {'red', 'amber', 'none'};
    ``corroborates`` is ``True`` when the condition requires ``>= 2`` independent signals
    before it may surface (only a corroborated stall does).
    """

    condition: Condition
    kind: str
    severity: str
    corroborates: bool


# The single source of truth for how each condition is coloured / corroborated. Red is
# reserved for the one FACT (aborted); every inference is amber and never red.
CORROBORATION: dict[Condition, Corroboration] = {
    Condition.ABORTED: Corroboration(Condition.ABORTED, "fact", "red", False),
    Condition.STALLED: Corroboration(Condition.STALLED, "inference", "amber", True),
    Condition.BLOCKED: Corroboration(Condition.BLOCKED, "inference", "amber", False),
    Condition.ACTIVE: Corroboration(Condition.ACTIVE, "fact", "none", False),
    Condition.IDLE: Corroboration(Condition.IDLE, "fact", "none", False),
}


def corroboration_for(condition: Condition) -> Corroboration:
    """The :class:`Corroboration` policy row for ``condition``."""
    return CORROBORATION[condition]


def is_corroborated_stall(
    signals: StallSignals, *, min_polls: int = _MIN_FREEZE_POLLS
) -> bool:
    """A stall is real ONLY when both signals agree: mtime stale AND content frozen.

    ``and`` short-circuits, so a fresh mtime is never a stall regardless of the freeze
    counter — one signal can never carry the inference.
    """
    return signals.mtime_stale and signals.frozen_polls >= min_polls


def classify_condition(
    *,
    aborted: bool,
    blocked: bool,
    active: bool,
    signals: StallSignals,
    min_polls: int = _MIN_FREEZE_POLLS,
) -> Condition:
    """Classify one unit, worst-first: aborted > corroborated-stall > blocked > active > idle.

    ``aborted`` is a fact and outranks everything; a stall is considered only when the
    two-signal gate is met; ``blocked`` (waiting, not frozen) is kept distinct from a stall;
    otherwise the unit is active or, as the floor, idle.
    """
    if aborted:
        return Condition.ABORTED
    if is_corroborated_stall(signals, min_polls=min_polls):
        return Condition.STALLED
    if blocked:
        return Condition.BLOCKED
    if active:
        return Condition.ACTIVE
    return Condition.IDLE


def should_render_red(condition: Condition) -> bool:
    """Whether ``condition`` may be drawn red — true only for the corroborated FACT.

    Reads :data:`CORROBORATION`, so no single-signal input (which can at most reach
    ``STALLED`` / ``BLOCKED``, both amber) can ever be red.
    """
    return corroboration_for(condition).severity == "red"


class StallTracker:
    """The cross-poll content-freeze counter — the SECOND (content) stall signal.

    :meth:`observe` returns how many CONSECUTIVE polls (including this one) carried an
    unchanged fingerprint: ``1`` on first sight or right after any change, ``2`` on the
    first repeat, and so on — so ``>= 2`` means "content has frozen for at least one poll".
    Deterministic and stdlib-only (no clock, no I/O), so it is fully testable.
    """

    def __init__(self) -> None:
        self._last: dict[str, object] = {}
        self._frozen: dict[str, int] = {}

    def observe(self, key: str, fingerprint: object) -> int:
        """Fold one poll's ``fingerprint`` for ``key``; return its consecutive-freeze count."""
        if key in self._last and self._last[key] == fingerprint:
            self._frozen[key] += 1
        else:
            self._frozen[key] = 1
        self._last[key] = fingerprint
        return self._frozen[key]

    def drop(self, key: str) -> None:
        """Forget ``key`` (a unit that left the fleet); a no-op for an unknown key."""
        self._last.pop(key, None)
        self._frozen.pop(key, None)
