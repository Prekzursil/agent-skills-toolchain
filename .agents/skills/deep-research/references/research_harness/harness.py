"""Thin orchestration glue for the deep-research harness (M-16).

Wires preflight -> routing into a single, *pure* planning step the skill can
call before dispatching searches. It deliberately does NOT make live MCP calls:
the actual provider fetch + caching + grading + report rendering happen in the
skill workflow using ``cache``, ``grading`` and ``report``. Keeping this layer
data-only makes the whole harness testable offline.

Sub-question DAG + effort classes (Lens 12 find 8): ``plan_research`` orders
sub-questions with ``graphlib`` so a dependent question ("market size of X")
runs after what it needs ("what is X"), classifies each into an effort class
(``fact`` / ``compare`` / ``deep`` = 3 / 8 / 15 calls, ``budget.EFFORT_CALLS``)
and sums the allotments so the caller can size the run ``Budget``. Decisions
keep their ORIGINAL index so the run ledger (``checkpoint``) lines up across a
resume, and sub-questions the ledger already answered are skipped.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter

from .budget import EFFORT_CALLS, EFFORT_COMPARE, EFFORT_DEEP, EFFORT_FACT
from .cache import normalize_query
from .preflight import ProviderStatus, down_servers, live_servers
from .routing import Provider, classify_capability, resolve_with_fallback

# Capabilities whose every sub-question is long-form by construction.
_DEEP_CAPABILITIES = frozenset({"deep_research", "council"})
_DEEP_KEYWORDS = (
    "landscape",
    "comprehensive",
    "exhaustive",
    "in-depth",
    "in depth",
    "deep research",
    "deep-research",
    "state of the art",
    "survey of",
    "everything about",
    "full picture",
)
_COMPARE_KEYWORDS = (
    "compare",
    "comparison",
    " vs ",
    " vs. ",
    "versus",
    "pros and cons",
    "trade-off",
    "tradeoff",
    "difference between",
    "differences between",
    "alternatives to",
    "which is better",
    "better than",
)


def classify_effort(subquestion: str, capability: str) -> str:
    """Effort class for a sub-question: ``fact`` (default), ``compare`` or ``deep``.

    A long-form capability is always ``deep``; otherwise a cheap keyword match
    (``deep`` checked before ``compare`` so a "comprehensive comparison" gets the
    bigger allotment); the ``synthesis`` capability defaults to ``compare``.
    """
    if capability in _DEEP_CAPABILITIES:
        return EFFORT_DEEP
    text = f" {' '.join(subquestion.lower().split())} "
    if any(keyword in text for keyword in _DEEP_KEYWORDS):
        return EFFORT_DEEP
    if capability == "synthesis" or any(
        keyword in text for keyword in _COMPARE_KEYWORDS
    ):
        return EFFORT_COMPARE
    return EFFORT_FACT


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """How one sub-question will be dispatched."""

    subquestion: str
    capability: str
    providers: tuple[Provider, ...]
    # Position in the ORIGINAL sub-question list (stable across a resume).
    index: int = 0
    # Original indexes this sub-question needs answered first.
    depends_on: tuple[int, ...] = ()
    effort: str = EFFORT_FACT
    call_allotment: int = EFFORT_CALLS[EFFORT_FACT]
    # Set when the capability's own chain had no live provider and a
    # ``routing.CAPABILITY_FALLBACKS`` capability answered instead.
    fallback_capability: str | None = None


@dataclass(frozen=True, slots=True)
class ResearchPlan:
    """The full routing plan plus the providers that were down at preflight."""

    decisions: tuple[RoutingDecision, ...]
    providers_down: tuple[str, ...]
    # Sub-questions dropped from ``decisions`` because a resumed ledger already
    # answered them (original text, input order).
    skipped: tuple[str, ...] = ()

    @property
    def routed_provider_keys(self) -> tuple[str, ...]:
        """Distinct provider keys across all decisions, in first-seen order."""
        seen: dict[str, None] = {}
        for decision in self.decisions:
            for provider in decision.providers:
                seen.setdefault(provider.key, None)
        return tuple(seen)

    @property
    def total_allotment(self) -> int:
        """Sum of per-sub-question call allotments: size ``Budget(max_calls=...)``."""
        return sum(decision.call_allotment for decision in self.decisions)


def _execution_order(count: int, depends_on: Mapping[int, Sequence[int]]) -> list[int]:
    """Topological order over original indexes; input order among peers."""
    sorter: TopologicalSorter[int] = TopologicalSorter()
    for index in range(count):
        sorter.add(index, *depends_on.get(index, ()))
    try:
        sorter.prepare()
    except CycleError as exc:
        raise ValueError(
            f"dependency cycle among sub-questions: {exc.args[1]}"
        ) from exc
    order: list[int] = []
    while sorter.is_active():
        ready = sorted(sorter.get_ready())
        order.extend(ready)
        sorter.done(*ready)
    return order


def plan_research(
    subquestions: list[str],
    statuses: dict[str, ProviderStatus],
    *,
    top_n: int = 2,
    depends_on: Mapping[int, Sequence[int]] | None = None,
    efforts: Mapping[int, str] | None = None,
    completed_subquestions: Collection[str] = (),
) -> ResearchPlan:
    """Classify + route each sub-question against the live-provider set.

    ``statuses`` is the preflight result (see ``preflight.run_preflight``).
    ``top_n`` caps providers per sub-question for cross-provider corroboration
    diversity (default 2). ``depends_on`` maps a sub-question index to the
    indexes it needs first (a DAG; cycles and out-of-range indexes raise
    ``ValueError``); ``efforts`` overrides the heuristic effort class per index;
    ``completed_subquestions`` (from ``checkpoint.resume``) are skipped.
    """
    depends_on = dict(depends_on or {})
    efforts = dict(efforts or {})
    count = len(subquestions)
    for index, deps in depends_on.items():
        bad = [d for d in (index, *deps) if not 0 <= d < count]
        if bad:
            raise ValueError(f"depends_on index out of range: {bad}")
    for index, effort in efforts.items():
        if not 0 <= index < count:
            raise ValueError(f"efforts index out of range: {index}")
        if effort not in EFFORT_CALLS:
            raise ValueError(f"unknown effort class {effort!r}")

    done = {normalize_query(q) for q in completed_subquestions}
    live = live_servers(statuses)
    decisions = []
    skipped = []
    for index in _execution_order(count, depends_on):
        subquestion = subquestions[index]
        if normalize_query(subquestion) in done:
            skipped.append(subquestion)
            continue
        capability = classify_capability(subquestion)
        providers, fallback = resolve_with_fallback(capability, live, top_n)
        effort = efforts.get(index) or classify_effort(subquestion, capability)
        decisions.append(
            RoutingDecision(
                subquestion=subquestion,
                capability=capability,
                providers=tuple(providers),
                index=index,
                depends_on=tuple(depends_on.get(index, ())),
                effort=effort,
                call_allotment=EFFORT_CALLS[effort],
                fallback_capability=fallback,
            )
        )
    skipped.sort(key=subquestions.index)
    return ResearchPlan(
        decisions=tuple(decisions),
        providers_down=tuple(down_servers(statuses)),
        skipped=tuple(skipped),
    )
