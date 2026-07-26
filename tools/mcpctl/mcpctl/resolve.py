"""PURE scope resolution: many scopes in, ONE scope-qualified state out.

The rule this module exists to enforce: **a resolved state is never a bare boolean.**
:class:`Resolution` always carries ``basis`` (every scope that contributed) and
``conflicts`` (human-readable notes when two scopes disagree), and marks itself
``inferred`` whenever more than one scope spoke. An operator reading a row can
therefore see *why* a server is off, which is the thing a single-scope read cannot
tell them -- and the thing whose absence previously cost a day.

Precedence is the MEASURED order in :data:`mcpctl.scopes.PRECEDENCE`. The one
counter-intuitive step is that ``mcpjson-approved`` sits BELOW both disable lists:
measured on this box, ``ghidra-mcp``, ``hexstrike-ai`` and ``ida-pro-mcp`` all appear
in ``enabledMcpjsonServers`` *and* in the root ``disabledMcpServers``, and none of the
three is live -- so approval does not override a disable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from mcpctl.scopes import ScopeId
from mcpctl.topology import Topology

__all__ = ["Resolution", "State", "resolve_state", "resolve_topology"]


class State(str, Enum):
    """The resolved state of one server. ``str``-valued for direct JSON output."""

    #: Defined and nothing suppresses it.
    ENABLED = "enabled"
    #: Suppressed by a ``disabledMcpServers`` list.
    DISABLED = "disabled"
    #: Suppressed by ``settings.json`` -> ``deniedMcpServers``.
    DENIED = "denied"
    #: Project-scope (``.mcp.json``) definition awaiting approval.
    PENDING_APPROVAL = "pending-approval"
    #: Mentioned by some scope but defined by none.
    UNDEFINED = "undefined"


_ADVISORY_NOTE = (
    "listed in loadout-template (.mcp-disabled-defaults.json), which is a template "
    "a tool copies INTO a project list -- advisory only, it decides nothing here"
)


@dataclass(frozen=True)
class Resolution:
    """A state plus the full audit trail that produced it."""

    state: State
    basis: tuple[ScopeId, ...] = ()
    conflicts: tuple[str, ...] = ()
    #: True when more than one scope contributed, i.e. the state is a JUDGEMENT over
    #: several sources rather than a single scope's plain reading.
    inferred: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "basis": [s.value for s in self.basis],
            "conflicts": list(self.conflicts),
            "inferred": self.inferred,
        }


def resolve_state(
    *,
    definitions: tuple[ScopeId, ...],
    mentions: tuple[ScopeId, ...],
    approved: bool,
    enable_all_project_servers: bool,
) -> Resolution:
    """Resolve one server. All inputs are explicit -- no ambient state is consulted."""
    mentioned = set(mentions)
    basis: list[ScopeId] = []
    conflicts: list[str] = []

    denied = ScopeId.SETTINGS_DENIED in mentioned
    project_disabled = ScopeId.CLAUDE_PROJECT_DISABLED in mentioned
    user_disabled = ScopeId.CLAUDE_USER_DISABLED in mentioned
    suppressors = [
        s
        for s, hit in (
            (ScopeId.SETTINGS_DENIED, denied),
            (ScopeId.CLAUDE_PROJECT_DISABLED, project_disabled),
            (ScopeId.CLAUDE_USER_DISABLED, user_disabled),
        )
        if hit
    ]

    if ScopeId.LOADOUT_TEMPLATE in mentioned:
        conflicts.append(_ADVISORY_NOTE)

    if suppressors:
        basis.extend(suppressors)
        if approved:
            conflicts.append(
                f"approved in {ScopeId.MCPJSON_APPROVED.value} but suppressed by "
                f"{', '.join(s.value for s in suppressors)}; MEASURED on this box: the "
                "suppression wins (ghidra-mcp / hexstrike-ai / ida-pro-mcp)"
            )
        state = State.DENIED if denied else State.DISABLED
        return Resolution(
            state=state,
            basis=tuple(basis),
            conflicts=tuple(conflicts),
            inferred=len(basis) > 1,
        )

    if not definitions:
        return Resolution(state=State.UNDEFINED, conflicts=tuple(conflicts))

    basis.extend(definitions)
    project_only = definitions == (ScopeId.MCP_JSON,)
    if project_only and not approved and not enable_all_project_servers:
        return Resolution(
            state=State.PENDING_APPROVAL,
            basis=tuple(basis),
            conflicts=tuple(conflicts),
            inferred=len(basis) > 1,
        )
    if project_only and approved:
        basis.append(ScopeId.MCPJSON_APPROVED)
    return Resolution(
        state=State.ENABLED,
        basis=tuple(basis),
        conflicts=tuple(conflicts),
        inferred=len(basis) > 1,
    )


def resolve_topology(top: Topology) -> Mapping[str, Resolution]:
    """Resolve every name the topology knows about."""
    approved = set(top.approved_mcpjson)
    return {
        name: resolve_state(
            definitions=top.scopes_of(name),
            mentions=top.mentions_of(name),
            approved=name in approved,
            enable_all_project_servers=top.enable_all_project_servers,
        )
        for name in top.names()
    }
