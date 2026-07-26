"""PURE health/status matrix: topology + injected liveness -> one row per server.

Every liveness input is INJECTED. This module never reads a process table, never opens
a socket, and never shells out; a caller that wants real numbers supplies them. That is
what keeps the 100% line+branch gate hermetic -- chasing coverage over an ambient
process probe would force live system state into CI.

A row deliberately carries BOTH the resolved state and the scopes that produced it, so
a reader can never mistake an inference for a plain reading.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from mcpctl.resolve import State, resolve_topology
from mcpctl.safety import EnvField, safe
from mcpctl.topology import Topology

__all__ = ["Liveness", "Row", "build_rows", "summarise"]


@dataclass(frozen=True)
class Liveness:
    """An observation about a server, supplied by the caller.

    All fields default to ``None`` meaning "not measured". ``None`` is NOT "zero" and
    NOT "dead": an unmeasured tool count must never render as a health verdict.
    """

    tool_count: int | None = None
    last_error: str | None = None
    pid: int | None = None
    rss_bytes: int | None = None


@dataclass(frozen=True)
class Row:
    """One rendered-ready server row. Every free-text field is already safe."""

    name: str
    scopes: tuple[str, ...]
    state: str
    basis: tuple[str, ...]
    inferred: bool
    transport: str
    env_fields: tuple[EnvField, ...] = ()
    conflicts: tuple[str, ...] = ()
    tool_count: int | None = None
    last_error: str | None = None
    pid: int | None = None
    rss_bytes: int | None = None

    @property
    def credential_bearing(self) -> bool:
        """True when at least one env var holds a literal value (a candidate secret)."""
        return any(f.kind == "present" for f in self.env_fields)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "scopes": list(self.scopes),
            "state": self.state,
            "basis": list(self.basis),
            "inferred": self.inferred,
            "transport": self.transport,
            "env_fields": [{"name": f.name, "kind": f.kind} for f in self.env_fields],
            "conflicts": list(self.conflicts),
            "tool_count": self.tool_count,
            "last_error": self.last_error,
            "pid": self.pid,
            "rss_bytes": self.rss_bytes,
        }


def build_rows(top: Topology, *, liveness: Mapping[str, Liveness]) -> tuple[Row, ...]:
    """Project the topology plus an injected liveness snapshot into sorted rows."""
    resolutions = resolve_topology(top)
    rows: list[Row] = []
    for name in top.names():
        resolution = resolutions[name]
        spec = top.spec_of(name)
        live = liveness.get(name, Liveness())
        rows.append(
            Row(
                name=name,
                scopes=tuple(s.value for s in top.scopes_of(name)),
                state=resolution.state.value,
                basis=tuple(s.value for s in resolution.basis),
                inferred=resolution.inferred,
                transport=spec.transport if spec is not None else "unknown",
                env_fields=spec.env_fields if spec is not None else (),
                conflicts=resolution.conflicts,
                tool_count=live.tool_count,
                last_error=None if live.last_error is None else safe(live.last_error),
                pid=live.pid,
                rss_bytes=live.rss_bytes,
            )
        )
    return tuple(rows)


def summarise(rows: tuple[Row, ...]) -> dict[str, int]:
    """Count rows per state, plus conflict and credential-bearing tallies."""
    counts = {"total": len(rows)}
    for state in State:
        counts[state.value] = sum(1 for r in rows if r.state == state.value)
    counts["with_conflicts"] = sum(1 for r in rows if r.conflicts)
    counts["credential_bearing"] = sum(1 for r in rows if r.credential_bearing)
    return counts
