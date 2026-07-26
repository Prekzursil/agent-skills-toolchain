"""The on-disk MCP configuration scopes and their MEASURED precedence.

Why this module exists
---------------------
A previous session lost a day to a single-scope read: it concluded a disable "took
effect" from ``disabledMcpServers`` being present at the ROOT of ``~/.claude.json``,
while the key that governed the session lived per-PROJECT. mcpctl therefore never
reduces a server to a bare enabled/disabled boolean -- every state carries the list of
scopes that produced it (see :mod:`mcpctl.resolve`).

Measured inventory, 2026-07-26, this box (counts are that day's observation, not a
contract; the scope SET and each key's SHAPE are the durable facts):

===================================================  ============================  ==============
file                                                 key                           shape / n
===================================================  ============================  ==============
``~/.claude.json``                                   ``mcpServers``                dict, n=66
``~/.claude.json`` (line 949)                        ``disabledMcpServers``        list[str], n=122
``~/.claude.json``                                   ``projects[<cwd>].disabledMcpServers``  list[str]
``~/.mcp.json``                                      ``mcpServers``                dict, n=14
``~/.claude/settings.local.json`` (line 41)          ``enabledMcpjsonServers``     list[str], n=12
``~/.claude/settings.local.json``                    ``enableAllProjectMcpServers``  bool, False
``~/.claude/settings.json`` (line 82)                ``deniedMcpServers``          **list[{"serverName": str}]**, n=5
``~/.claude/.mcp-disabled-defaults.json``            ``disabledMcpServers``        list[str], n=85
===================================================  ============================  ==============

Two shapes bite a naive reader:

* ``deniedMcpServers`` holds **objects**, not strings (observed element:
  ``{"serverName": "markitdown"}``). A ``set(list_of_str)`` reader raises
  ``TypeError`` or silently yields nothing -- ``tools/mcp-manager`` does not read this
  key at all, so its inventory is blind to those 5 denials.
* ``projects`` is keyed by the session's EXACT cwd. An ancestor directory's row does
  NOT apply. Measured: for cwd
  ``C:/Users/Prekzursil/.claude/agent-worktrees/agent-364079870`` there is no row,
  while the ancestor row ``C:/Users/Prekzursil`` carries n=117 -- a different project.
  Attributing that 117 to the session would be wrong in both directions.

``.mcp-disabled-defaults.json`` is a *template*, not a scope Claude Code consults: it
is a loadout that a tool copies INTO a project's ``disabledMcpServers``. mcpctl labels
it ``ADVISORY`` and never lets it decide a state.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["DEFINITION_SCOPES", "PRECEDENCE", "ScopeId", "VERDICT_SCOPES"]


class ScopeId(str, Enum):
    """One configuration scope. ``str``-valued so it serialises as itself in JSON."""

    #: ``~/.claude.json`` -> ``mcpServers`` (user scope). A definition scope.
    CLAUDE_USER = "claude-user"
    #: ``~/.mcp.json`` -> ``mcpServers`` (project scope for the home directory).
    MCP_JSON = "mcp-json"
    #: ``~/.claude.json`` -> ``disabledMcpServers`` (root).
    CLAUDE_USER_DISABLED = "claude-user-disabled"
    #: ``~/.claude.json`` -> ``projects[<exact cwd>].disabledMcpServers``.
    CLAUDE_PROJECT_DISABLED = "claude-project-disabled"
    #: ``~/.claude/settings.local.json`` -> ``enabledMcpjsonServers``.
    MCPJSON_APPROVED = "mcpjson-approved"
    #: ``~/.claude/settings.json`` -> ``deniedMcpServers`` (list of objects).
    SETTINGS_DENIED = "settings-denied"
    #: ``~/.claude/.mcp-disabled-defaults.json`` -> ``disabledMcpServers``. ADVISORY.
    LOADOUT_TEMPLATE = "loadout-template"


#: Scopes that DEFINE a server (i.e. supply its transport/command).
DEFINITION_SCOPES: tuple[ScopeId, ...] = (ScopeId.CLAUDE_USER, ScopeId.MCP_JSON)

#: Scopes that ASSERT something about whether a server should run.
VERDICT_SCOPES: tuple[ScopeId, ...] = (
    ScopeId.SETTINGS_DENIED,
    ScopeId.CLAUDE_PROJECT_DISABLED,
    ScopeId.CLAUDE_USER_DISABLED,
    ScopeId.MCPJSON_APPROVED,
    ScopeId.LOADOUT_TEMPLATE,
)

#: Verdict scopes in decreasing authority. MEASURED ordering, not assumed:
#:
#: * ``SETTINGS_DENIED`` first -- an explicit per-server denial recorded by the host.
#: * ``CLAUDE_PROJECT_DISABLED`` above ``CLAUDE_USER_DISABLED`` because the per-project
#:   list is the one the host writes on a curation action, and it is applied only when
#:   a row for the EXACT cwd exists.
#: * ``MCPJSON_APPROVED`` below both disable lists. This is the measurement that
#:   refuted the natural guess: ``ghidra-mcp``, ``hexstrike-ai`` and ``ida-pro-mcp``
#:   are all listed in ``enabledMcpjsonServers`` AND in the root
#:   ``disabledMcpServers``, and none of the three is live -- so approval does NOT
#:   override a disable. (Detector control: 43/43 root-disabled servers defined only
#:   in ``~/.claude.json`` were likewise absent, so the liveness probe can see the
#:   "disabled" state it is being asked about.)
#: * ``LOADOUT_TEMPLATE`` last and advisory-only; it never decides a state.
PRECEDENCE: tuple[ScopeId, ...] = (
    ScopeId.SETTINGS_DENIED,
    ScopeId.CLAUDE_PROJECT_DISABLED,
    ScopeId.CLAUDE_USER_DISABLED,
    ScopeId.MCPJSON_APPROVED,
    ScopeId.LOADOUT_TEMPLATE,
)
