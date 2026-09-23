"""Per-sub-question sufficiency gate + one bounded follow-up (Lens 12 find 6).

Grading (``grading.py``) is per *source*; nothing said "this sub-question has
enough". CRAG / Sufficient Context show RAG systems "hallucinate more than
abstain" when the retrieved set is thin, so this gate sits between fusion and
writing. Deterministic, from signals that already exist:

    sufficient   >= 2 sources graded >= B  AND  >= 1 of them corroborated
    partial      >= 1 strong source but the bar above is not met
    insufficient no source graded >= B

Not sufficient -> exactly ONE reformulated follow-up query (deterministic: the
question lead is stripped, entities are quoted for exact match, dates kept, a
"primary source" hint appended), then the sub-question is marked **open** and
the run's terminal state becomes ``partial:sources``. Both a quality lift and a
budget cap: it turns "write anyway" into "one targeted retry, else declare open".
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from .cache import normalize_query
from .grading import TIER_A, TIER_B, Grade
from .report import STATUS_PARTIAL_SOURCES

SUFFICIENT = "sufficient"
PARTIAL = "partial"
INSUFFICIENT = "insufficient"

MIN_STRONG_SOURCES = 2
MIN_CORROBORATED = 1
MAX_FOLLOW_UPS = 1
STRONG_TIERS = frozenset({TIER_A, TIER_B})

ACTION_WRITE = "write"
ACTION_FOLLOW_UP = "follow_up"
ACTION_MARK_OPEN = "mark_open"

_QUESTION_LEAD_RE = re.compile(
    r"^(?:what|which|who|whom|whose|when|where|why|how)\b"
    r"(?:\s+(?:is|are|was|were|do|does|did|has|have|had|can|could|should|would|will|"
    r"many|much|often|long|far))*\s*",
    re.IGNORECASE,
)
_ENTITY_RE = re.compile(r"\b[A-Z][\w-]*(?:\s+[A-Z][\w-]*)*")
_HINTS = ("primary source", "official report", "site:gov OR site:edu")


@dataclass(frozen=True, slots=True)
class SufficiencyVerdict:
    verdict: str
    strong_sources: int
    corroborated: int
    total_sources: int

    @property
    def sufficient(self) -> bool:
        return self.verdict == SUFFICIENT


def judge_sufficiency(grades: Sequence[Grade]) -> SufficiencyVerdict:
    """Aggregate per-source grades into one per-sub-question verdict."""
    strong = [g for g in grades if g.tier in STRONG_TIERS]
    corroborated = sum(1 for g in strong if g.corroboration_count >= 2)
    if len(strong) >= MIN_STRONG_SOURCES and corroborated >= MIN_CORROBORATED:
        verdict = SUFFICIENT
    elif strong:
        verdict = PARTIAL
    else:
        verdict = INSUFFICIENT
    return SufficiencyVerdict(
        verdict=verdict,
        strong_sources=len(strong),
        corroborated=corroborated,
        total_sources=len(grades),
    )


def follow_up_query(
    subquestion: str, *, attempts: int, seen: Collection[str] = ()
) -> str | None:
    """One deterministic reformulation; ``None`` once the follow-up is spent.

    ``seen`` (queries already dispatched for this sub-question) steers the hint
    so the retry is never the query that just came back thin.
    """
    if attempts < 0:
        raise ValueError("attempts must be >= 0")
    if attempts >= MAX_FOLLOW_UPS:
        return None
    core = _QUESTION_LEAD_RE.sub(
        "", subquestion.strip().rstrip("?.! "), count=1
    ).strip()
    for phrase in sorted(set(_ENTITY_RE.findall(core)), key=len, reverse=True):
        if f'"{phrase}"' not in core:
            core = core.replace(phrase, f'"{phrase}"')
    seen_norm = {normalize_query(q) for q in seen}
    for hint in _HINTS:
        candidate = f"{core} {hint}".strip()
        if normalize_query(candidate) not in seen_norm:
            return candidate
    return None


@dataclass(frozen=True, slots=True)
class GateDecision:
    action: str  # write | follow_up | mark_open
    verdict: SufficiencyVerdict
    query: str | None = None

    @property
    def status(self) -> str | None:
        """Terminal-state contribution: ``partial:sources`` when left open."""
        return STATUS_PARTIAL_SOURCES if self.action == ACTION_MARK_OPEN else None


def gate(
    subquestion: str,
    grades: Sequence[Grade],
    *,
    attempts: int = 0,
    seen: Collection[str] = (),
) -> GateDecision:
    """Decide: write, run the one bounded follow-up, or mark the sub-question open."""
    if attempts < 0:
        raise ValueError("attempts must be >= 0")
    verdict = judge_sufficiency(grades)
    if verdict.sufficient:
        return GateDecision(ACTION_WRITE, verdict)
    query = follow_up_query(subquestion, attempts=attempts, seen=seen)
    if query is not None:
        return GateDecision(ACTION_FOLLOW_UP, verdict, query)
    return GateDecision(ACTION_MARK_OPEN, verdict)
