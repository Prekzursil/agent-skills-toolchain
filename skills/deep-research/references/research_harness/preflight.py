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

# Servers that are routed AROUND, never retried, once they probe non-live
# within a run (G-5b). Perplexity is cookie/session-auth: a DOWN there means
# the session cookie expired or the plan is rate-limited, and retrying only
# burns wall-clock (and, on the deep-research lanes, metered quota). The fix is
# an owner action (refresh ``PERPLEXITY_SESSION_TOKEN``), not a retry.
NO_RETRY_SERVERS = frozenset({"perplexity"})

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


def retry_allowed(status: ProviderStatus) -> bool:
    """May the loop re-probe / re-call this server later in the same run?

    ``QUOTA`` is never retried (the quota does not come back mid-run), and a
    ``NO_RETRY_SERVERS`` member is never retried once it is anything but
    ``LIVE``: route around it and record it in ``providers_down``. A plain
    ``DOWN`` elsewhere may be a transient and is left to the caller's judgment.
    """
    if status.state == QUOTA:
        return False
    if status.server in NO_RETRY_SERVERS and status.state != LIVE:
        return False
    return True
