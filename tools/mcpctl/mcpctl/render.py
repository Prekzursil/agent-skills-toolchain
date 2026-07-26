"""PURE text renderers for the matrix, the credential map, and the topology.

Rendering is deliberately plain fixed-width text: no colour, no ANSI, no cursor
control. mcpctl emits terminal-bound text built from partly attacker-influenceable
data (a server NAME is free text in a config file), and the cheapest way to guarantee
no escape ever reaches the terminal is to never emit one and to strip every control
byte on the way in (:mod:`mcpctl.safety`). Widths are computed on already-stripped
strings, so a truncation can never slice through the middle of an escape.
"""

from __future__ import annotations

from mcpctl.matrix import Row
from mcpctl.scopes import PRECEDENCE, ScopeId
from mcpctl.topology import Topology

__all__ = [
    "render_conflicts",
    "render_credentials",
    "render_matrix",
    "render_topology",
]

_NAME_W = 24
_STATE_W = 17
_TRANSPORT_W = 10
_TOOLS_W = 6
_SCOPES_W = 26


def _cell(text: str, width: int) -> str:
    if len(text) > width:
        return text[: width - 1] + "."
    return text.ljust(width)


def render_matrix(rows: tuple[Row, ...]) -> str:
    """Render the health/status matrix as a fixed-width table.

    An inferred state is suffixed ``~`` so a judgement over several scopes is never
    read as a single scope's plain statement. An unmeasured tool count renders ``-``,
    never ``0`` -- "not measured" and "zero tools" are different facts.
    """
    if not rows:
        return "no MCP servers found in any configuration scope"
    header = (
        f"{_cell('SERVER', _NAME_W)}{_cell('STATE', _STATE_W)}"
        f"{_cell('TRANSPORT', _TRANSPORT_W)}{_cell('TOOLS', _TOOLS_W)}"
        f"{_cell('SCOPES', _SCOPES_W)}BASIS"
    )
    lines = [header, "-" * (len(header) + 8)]
    for row in rows:
        state = row.state + ("~" if row.inferred else "")
        tools = "-" if row.tool_count is None else str(row.tool_count)
        lines.append(
            f"{_cell(row.name, _NAME_W)}{_cell(state, _STATE_W)}"
            f"{_cell(row.transport, _TRANSPORT_W)}{_cell(tools, _TOOLS_W)}"
            f"{_cell(','.join(row.scopes) or '-', _SCOPES_W)}"
            f"{','.join(row.basis) or '-'}"
        )
    lines.append("")
    lines.append("~ = inferred from more than one scope (see the BASIS column)")
    return "\n".join(lines)


def render_credentials(rows: tuple[Row, ...]) -> str:
    """Render the credential map: variable NAMES and classifications, never values."""
    bearing = [r for r in rows if r.env_fields]
    if not bearing:
        return "no env-bearing MCP servers in any configuration scope"
    lines = [
        "credential map -- VARIABLE NAMES ONLY; mcpctl never parses or prints a value",
        "",
    ]
    for row in bearing:
        lines.append(row.name)
        for env in row.env_fields:
            lines.append(f"    {env.name}: {env.kind}")
    return "\n".join(lines)


def render_conflicts(rows: tuple[Row, ...]) -> str:
    """Render every scope conflict, grouped by server."""
    conflicting = [r for r in rows if r.conflicts]
    if not conflicting:
        return "no scope conflicts detected"
    lines: list[str] = []
    for row in conflicting:
        lines.append(row.name)
        for note in row.conflicts:
            lines.append(f"    - {note}")
    return "\n".join(lines)


def render_topology(top: Topology) -> str:
    """Render which scopes were seen, how many names each holds, and the precedence."""
    definition_counts = {
        scope: sum(1 for n in top.names() if scope in top.scopes_of(n))
        for scope in (ScopeId.CLAUDE_USER, ScopeId.MCP_JSON)
    }
    mention_counts = {
        scope: sum(1 for n in top.names() if scope in top.mentions_of(n))
        for scope in PRECEDENCE
    }
    row_status = "FOUND" if top.project_row_found else "NOT FOUND"
    lines = [
        "MCP configuration topology",
        "",
        f"project key requested : {top.project_key}",
        f"project row: {row_status} (an ANCESTOR directory's row is never substituted)",
        f"enableAllProjectMcpServers: {top.enable_all_project_servers}",
        f"approved .mcp.json servers: {len(top.approved_mcpjson)}",
        "",
        "definition scopes:",
    ]
    for scope, count in definition_counts.items():
        lines.append(f"    {scope.value:<26} {count} server(s)")
    lines.append("")
    lines.append("verdict scopes (highest authority first):")
    for scope in PRECEDENCE:
        advisory = (
            "  [ADVISORY -- decides nothing]"
            if scope is ScopeId.LOADOUT_TEMPLATE
            else ""
        )
        lines.append(f"    {scope.value:<26} {mention_counts[scope]} name(s){advisory}")
    lines.append("")
    lines.append(
        "precedence: "
        + " > ".join(s.value for s in PRECEDENCE if s is not ScopeId.LOADOUT_TEMPLATE)
    )
    return "\n".join(lines)
