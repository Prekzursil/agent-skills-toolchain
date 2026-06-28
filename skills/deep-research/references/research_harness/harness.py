"""Thin orchestration glue for the deep-research harness (M-16).

Wires preflight -> routing into a single, *pure* planning step the skill can
call before dispatching searches. It deliberately does NOT make live MCP calls:
the actual provider fetch + caching + grading + report rendering happen in the
skill workflow using ``cache``, ``grading`` and ``report``. Keeping this layer
data-only makes the whole harness testable offline.
"""

from dataclasses import dataclass

from .preflight import ProviderStatus, down_servers, live_servers
from .routing import Provider, route_subquestion


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """How one sub-question will be dispatched."""

    subquestion: str
    capability: str
    providers: tuple[Provider, ...]


@dataclass(frozen=True, slots=True)
class ResearchPlan:
    """The full routing plan plus the providers that were down at preflight."""

    decisions: tuple[RoutingDecision, ...]
    providers_down: tuple[str, ...]

    @property
    def routed_provider_keys(self) -> tuple[str, ...]:
        """Distinct provider keys across all decisions, in first-seen order."""
        seen: dict[str, None] = {}
        for decision in self.decisions:
            for provider in decision.providers:
                seen.setdefault(provider.key, None)
        return tuple(seen)


def plan_research(
    subquestions: list[str],
    statuses: dict[str, ProviderStatus],
    *,
    top_n: int = 2,
) -> ResearchPlan:
    """Classify + route each sub-question against the live-provider set.

    ``statuses`` is the preflight result (see ``preflight.run_preflight``).
    ``top_n`` caps providers per sub-question for cross-provider corroboration
    diversity (default 2).
    """
    live = live_servers(statuses)
    decisions = []
    for subquestion in subquestions:
        capability, providers = route_subquestion(subquestion, live, top_n)
        decisions.append(
            RoutingDecision(
                subquestion=subquestion,
                capability=capability,
                providers=tuple(providers),
            )
        )
    return ResearchPlan(
        decisions=tuple(decisions),
        providers_down=tuple(down_servers(statuses)),
    )
