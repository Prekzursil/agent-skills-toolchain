"""Struggle / loop guard for the deep-research harness (Lens 12 find 5).

Deep Research Bench finds "repeated tool calls" the dominant action failure;
Context Rot shows give-ups concentrate where the struggle score is high. Both
are the most machine-detectable failure the harness has, and the cheapest to
stop: repeated near-identical queries burn exactly the budget a RAM-starved box
lacks. The query cache happily returns the same cached result to a looping
agent; this module blocks the loop itself.

Two deterministic signals, both reusing what already exists:

* **Repeated query** - the exact ``cache.query_hash`` has been seen, or the
  token-Jaccard similarity against a recent query is >= ``LOOP_THRESHOLD``
  (0.8). After ``max_repeats`` such repeats the run is ``partial:loop``.
* **No progress** - ``no_progress_rounds`` consecutive rounds with zero new
  unique URLs for a sub-question -> mark it open and move on.

Pure, in-memory, per run. ~40 lines of logic; the rest is bookkeeping.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass

from .academic import canonical_url
from .cache import normalize_query, query_hash
from .report import STATUS_PARTIAL_LOOP

LOOP_THRESHOLD = 0.8
DEFAULT_MAX_REPEATS = 2
DEFAULT_NO_PROGRESS_ROUNDS = 2
DEFAULT_WINDOW = 50

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> frozenset[str]:
    """Lower-case alphanumeric token set (punctuation is a separator)."""
    return frozenset(_TOKEN_RE.findall(text.lower()))


def token_jaccard(a: str, b: str) -> float:
    """|A & B| / |A | B| over token sets; 0.0 when both are empty."""
    ta, tb = tokenize(a), tokenize(b)
    union = ta | tb
    if not union:
        return 0.0
    return len(ta & tb) / len(union)


@dataclass(frozen=True, slots=True)
class LoopVerdict:
    """Outcome of observing one query."""

    query: str
    repeated: bool
    similarity: float
    nearest: str | None
    repeats: int
    tripped: bool

    @property
    def status(self) -> str | None:
        return STATUS_PARTIAL_LOOP if self.tripped else None


@dataclass(frozen=True, slots=True)
class ProgressVerdict:
    """Outcome of observing one round of results for a sub-question."""

    subquestion: str
    new_urls: int
    stalled_rounds: int
    mark_open: bool


class LoopGuard:
    """Per-run detector for repeated queries and stalled sub-questions."""

    def __init__(
        self,
        *,
        threshold: float = LOOP_THRESHOLD,
        max_repeats: int = DEFAULT_MAX_REPEATS,
        no_progress_rounds: int = DEFAULT_NO_PROGRESS_ROUNDS,
        window: int = DEFAULT_WINDOW,
    ) -> None:
        if not 0.0 < threshold <= 1.0:
            raise ValueError("threshold must be in (0, 1]")
        if max_repeats < 1 or no_progress_rounds < 1 or window < 1:
            raise ValueError("max_repeats, no_progress_rounds and window must be >= 1")
        self.threshold = threshold
        self.max_repeats = max_repeats
        self.no_progress_rounds = no_progress_rounds
        self._seen_hashes: set[str] = set()
        self._recent: deque[str] = deque(maxlen=window)
        self._repeats = 0
        self._urls_seen: dict[str, set[str]] = {}
        self._stalled: dict[str, int] = {}

    # --- repeated queries ---------------------------------------------------
    def observe(
        self, query: str, *, capability: str = "", provider: str = ""
    ) -> LoopVerdict:
        """Record a query about to be dispatched and say whether it is a repeat."""
        qhash = query_hash(capability, provider, query)
        exact = qhash in self._seen_hashes
        similarity, nearest = 0.0, None
        for previous in self._recent:
            score = token_jaccard(query, previous)
            if score > similarity:
                similarity, nearest = score, previous
        if exact:
            similarity, nearest = 1.0, nearest or query
        repeated = exact or similarity >= self.threshold
        if repeated:
            self._repeats += 1
        self._seen_hashes.add(qhash)
        self._recent.append(normalize_query(query))
        return LoopVerdict(
            query=query,
            repeated=repeated,
            similarity=similarity,
            nearest=nearest,
            repeats=self._repeats,
            tripped=self._repeats >= self.max_repeats,
        )

    @property
    def repeats(self) -> int:
        return self._repeats

    @property
    def tripped(self) -> bool:
        return self._repeats >= self.max_repeats

    @property
    def status(self) -> str | None:
        return STATUS_PARTIAL_LOOP if self.tripped else None

    # --- stalled sub-questions ----------------------------------------------
    def observe_results(
        self, subquestion: str, urls: list[str] | tuple[str, ...]
    ) -> ProgressVerdict:
        """Record a round's URLs; two zero-new rounds in a row -> mark it open."""
        key = normalize_query(subquestion)
        seen = self._urls_seen.setdefault(key, set())
        fresh = {canonical_url(u) or u for u in urls if u} - seen
        seen.update(fresh)
        if fresh:
            self._stalled[key] = 0
        else:
            self._stalled[key] = self._stalled.get(key, 0) + 1
        stalled = self._stalled[key]
        return ProgressVerdict(
            subquestion=subquestion,
            new_urls=len(fresh),
            stalled_rounds=stalled,
            mark_open=stalled >= self.no_progress_rounds,
        )
