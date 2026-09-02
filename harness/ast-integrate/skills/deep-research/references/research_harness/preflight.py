"""Provider preflight for the deep-research harness (M-16).

Generalizes the ``external-tools-health`` / mcp_doctor pattern: before a run,
probe which providers are actually reachable / in quota, and route only to live
ones (graceful degradation instead of a mid-run failure on a dead MCP).

This module is *pure*: the actual liveness probe is injected as a callable so
the harness builds and tests fully offline. The probe must be READ-ONLY and
must respect operational guardrails (never disturb the live GUI IDA MCP on
:13337; never call Sci-Hub). Those servers are not in the research routing
table, so the default server set already excludes them.
"""

from collections.abc import Callable
from dataclasses import dataclass

from .routing import ROUTING_TABLE, is_excluded

LIVE = "live"
DOWN = "down"
QUOTA = "quota"

ProbeFn = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    """Liveness verdict for one MCP server."""

    server: str
    state: str  # LIVE | DOWN | QUOTA


def routable_servers() -> set[str]:
    """Every distinct, non-excluded server referenced by the routing table."""
    servers: set[str] = set()
    for providers in ROUTING_TABLE.values():
        for provider in providers:
            if not is_excluded(provider):
                servers.add(provider.server)
    return servers


def run_preflight(
    probe: ProbeFn, servers: set[str] | None = None
) -> dict[str, ProviderStatus]:
    """Probe each server, returning a server -> status map.

    ``probe(server)`` returns one of ``LIVE`` / ``DOWN`` / ``QUOTA``. Any probe
    exception is treated as ``DOWN`` (fail-safe: route around it).
    """
    targets = routable_servers() if servers is None else servers
    statuses: dict[str, ProviderStatus] = {}
    for server in sorted(targets):
        try:
            state = probe(server)
        except Exception:  # noqa: BLE001 - a flaky probe must not abort preflight
            state = DOWN
        if state not in (LIVE, DOWN, QUOTA):
            state = DOWN
        statuses[server] = ProviderStatus(server=server, state=state)
    return statuses


def live_servers(statuses: dict[str, ProviderStatus]) -> set[str]:
    """Set of servers that probed LIVE (the routable set)."""
    return {s.server for s in statuses.values() if s.state == LIVE}


def down_servers(statuses: dict[str, ProviderStatus]) -> list[str]:
    """Sorted servers that were DOWN or QUOTA-exhausted at preflight."""
    return sorted(s.server for s in statuses.values() if s.state != LIVE)
