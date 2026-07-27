"""``pane_views`` — the five concrete cockpit panes, each a THIN adapter over one source.

Every pane here is deliberately small: it reads an ALREADY-POLLED snapshot, formats rows and
hands them back. No pane opens a file, a socket or a clock — the reuse rule is absolute:

===============  ====================================================================
pane             the existing source it renders
===============  ====================================================================
``codex``        :class:`monitorcore.codex_source.CodexSource` → re-uses the WHOLE Phase-1
                 renderer (:func:`monitorcore.group_tree.derive_groups` +
                 :func:`monitorcore.view.render_view`), so the drill view is not forked.
``agents``       :class:`monitorcore.agents_source.AgentsSource` (which is itself a wrapper
                 over :func:`monitorcore.discovery.scan` — no second transcript walk).
``workflows``    the SAME ``agents`` snapshot, re-projected by workflow id. One poll, two
                 panes: a workflow row is a rollup of the agents that workflow owns.
``databricks``   :class:`monitorcore.databricks_source.DatabricksSource`, re-using its
                 measured :func:`~monitorcore.databricks_source.busy_glyph`.
``mcp``          :class:`monitorcore.mcp_source.McpSource` — inventory only; every health
                 column prints ``not-measured``.
===============  ====================================================================

Degradation is uniform and explicit. A pane whose source is **not registered** or **not
reachable** renders a single :func:`monitorcore.pane.not_measured` row and reports ZERO
selectable rows — it never fabricates an empty list that would read as "healthy and idle".
A source that WAS reached and legitimately holds nothing renders a separate "nothing
observed" notice, because a measured zero and an unmeasured field are different facts.

Glyphs follow the existing width policy (:func:`monitorcore.responsive.layout_for`), so a
narrow terminal degrades to ASCII exactly as the Phase-1 board does. Pure over its inputs.
"""

from __future__ import annotations

from dataclasses import replace

from .agents_source import AgentRow, AgentsSource, workflow_key
from .codex_source import CodexSource
from .contract import Snapshot
from .databricks_source import DatabricksSource, DbxUnit, busy_glyph
from .group_tree import derive_groups
from .mcp_source import McpServer, McpSource
from .nav import ViewState, nav_items, visible_groups
from .pane import (
    Pane,
    PaneBody,
    PaneCtx,
    PaneId,
    clamp,
    cursor_rows,
    not_measured,
    payload_rows,
    safe,
)
from .responsive import layout_for
from .view import render_view

__all__ = [
    "PANES",
    "AgentsPane",
    "CodexPane",
    "DatabricksPane",
    "McpPane",
    "WorkflowsPane",
    "age_label",
    "measured",
]

_GLYPHS = {"running": "▶", "idle": "·", "done": "✔", "error": "✖"}
_ASCII_GLYPHS = {"running": ">", "idle": ".", "done": "+", "error": "x"}
_UNKNOWN_GLYPH = "?"

#: What an unmeasured scalar prints as. Never ``0``, never blank — see ``pane`` invariant 2.
NOT_MEASURED_SHORT = "not-measured"


def age_label(seconds: float) -> str:
    """A compact age: ``42s`` / ``7m`` / ``3.1h`` (negative clock skew clamps to ``0s``)."""
    if seconds < 0:
        return "0s"
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.0f}m"
    return f"{seconds / 3600:.1f}h"


def measured(value: object) -> str:
    """``str(value)``, or :data:`NOT_MEASURED_SHORT` when the value is ``None``."""
    if value is None:
        return NOT_MEASURED_SHORT
    return safe(value)


def _glyphs(cols: int) -> dict[str, str]:
    """The bucket→glyph map for this width, via the EXISTING breakpoint policy."""
    return _ASCII_GLYPHS if layout_for(cols).ascii else _GLYPHS


def _notice(text: str, ctx: PaneCtx) -> PaneBody:
    """A single non-selectable informational row (no cursor, zero selectable rows)."""
    return PaneBody(cursor_rows([safe(text)], replace(ctx, cursor=False)), 0)


def _degraded(
    label: str, snap: Snapshot[object] | None, ctx: PaneCtx
) -> PaneBody | None:
    """The NOT-MEASURED body when the source is missing/unreachable, else ``None``.

    Returning ``None`` means "the source was reached — render its real rows", which is the
    only path allowed to print a zero.
    """
    if snap is None:
        return _notice(not_measured(label, "no source registered"), ctx)
    if not snap.reachable:
        detail = safe(snap.error) or "source unreachable"
        return _notice(not_measured(label, detail), ctx)
    return None


class CodexPane:
    """The Phase-1 Codex drill view, unchanged — this pane only routes to it."""

    id: str = PaneId.CODEX
    title: str = "codex"
    source_id: str = CodexSource.id

    def body(self, snap: Snapshot[object] | None, ctx: PaneCtx) -> PaneBody:
        degraded = _degraded("codex threads", snap, ctx)
        if degraded is not None:
            return degraded
        threads = payload_rows(snap, "threads")
        if not threads:
            return _notice("no codex threads in the window", ctx)
        groups = derive_groups(threads)
        count = len(nav_items(visible_groups(groups, ViewState())))
        state = ViewState(selected=clamp(ctx.selected, count))
        lines = render_view(groups, state, ctx.now, ctx.cols, cursor=ctx.cursor)
        return PaneBody(tuple(lines), count)


class AgentsPane:
    """One row per Claude subagent transcript found by the existing discovery scan."""

    id: str = PaneId.AGENTS
    title: str = "agents"
    source_id: str = AgentsSource.id

    def body(self, snap: Snapshot[object] | None, ctx: PaneCtx) -> PaneBody:
        degraded = _degraded("subagents", snap, ctx)
        if degraded is not None:
            return degraded
        rows = payload_rows(snap, "rows")
        if not rows:
            return _notice("no subagent transcripts observed", ctx)
        glyphs = _glyphs(ctx.cols)
        lines = [_agent_line(row, glyphs) for row in rows]
        return PaneBody(cursor_rows(lines, ctx), len(lines))


def _agent_line(row: AgentRow, glyphs: dict[str, str]) -> str:
    """``▶ [RUNNING] scout · general-purpose · wf_bfc0 · 12s idle · 📝 reading the plan``.

    Free-text fields are TRUNCATED, not padded: the last-mile :func:`monitorcore.codex_tail
    .clip` whitespace-collapses every row, so column padding would be silently discarded —
    the same ``·``-separated house style :func:`monitorcore.codex_tail.board_line` uses.
    """
    glyph = glyphs.get(row.bucket, _UNKNOWN_GLYPH)
    return (
        f"{glyph} [{safe(row.bucket).upper()}] {safe(row.name):.28} · "
        f"{safe(row.agent_type):.20} · {safe(row.wf) or '-':.24} · "
        f"{age_label(row.age_s)} idle · {safe(row.last)}"
    )


class WorkflowsPane:
    """A rollup of the SAME agents snapshot, one row per owning workflow."""

    id: str = PaneId.WORKFLOWS
    title: str = "workflows"
    source_id: str = AgentsSource.id

    def body(self, snap: Snapshot[object] | None, ctx: PaneCtx) -> PaneBody:
        degraded = _degraded("workflows", snap, ctx)
        if degraded is not None:
            return degraded
        rows = payload_rows(snap, "rows")
        if not rows:
            return _notice("no workflow-owned agents observed", ctx)
        buckets: dict[str, list[AgentRow]] = {}
        for row in rows:
            buckets.setdefault(workflow_key(row), []).append(row)
        glyphs = _glyphs(ctx.cols)
        lines = [_workflow_line(key, buckets[key], glyphs) for key in sorted(buckets)]
        return PaneBody(cursor_rows(lines, ctx), len(lines))


def _workflow_line(key: str, members: list[AgentRow], glyphs: dict[str, str]) -> str:
    """``▶ wf_bfc00235    6 agents   2 running   0 error   12s``."""
    running = sum(1 for m in members if m.bucket == "running")
    errors = sum(1 for m in members if m.bucket == "error")
    newest = min(m.age_s for m in members)
    if errors:
        bucket = "error"
    elif running:
        bucket = "running"
    else:
        bucket = "idle"
    return (
        f"{glyphs.get(bucket, _UNKNOWN_GLYPH)} {safe(key):.36} · {len(members)} agents · "
        f"{running} running · {errors} error · {age_label(newest)} idle"
    )


class DatabricksPane:
    """One row per Databricks fan-out unit, using the source's measured busy glyph."""

    id: str = PaneId.DATABRICKS
    title: str = "databricks"
    source_id: str = DatabricksSource.id

    def body(self, snap: Snapshot[object] | None, ctx: PaneCtx) -> PaneBody:
        degraded = _degraded("databricks units", snap, ctx)
        if degraded is not None:
            return degraded
        units = payload_rows(snap, "units")
        if not units:
            return _notice("no units observed in the event stream", ctx)
        lines = [_unit_line(unit) for unit in units]
        return PaneBody(cursor_rows(lines, ctx), len(lines))


def _unit_line(unit: DbxUnit) -> str:
    """``● u-0007   running    run-42        idle=8s   <error>``.

    The glyph is the source's OWN measured :func:`~monitorcore.databricks_source.busy_glyph`
    (arrival-derived), never a constant this pane invents.
    """
    error = safe(unit.error)
    tail = f" · {error:.60}" if error else ""
    return (
        f"{busy_glyph(unit)} [{safe(unit.liveness)}] {safe(unit.unit_id):.32} · "
        f"{safe(unit.run_id):.24} · idle={age_label(unit.idle_s)}{tail}"
    )


class McpPane:
    """The declared MCP inventory. Health columns print ``not-measured``, never ``0``."""

    id: str = PaneId.MCP
    title: str = "mcp"
    source_id: str = McpSource.id

    def body(self, snap: Snapshot[object] | None, ctx: PaneCtx) -> PaneBody:
        degraded = _degraded("mcp inventory", snap, ctx)
        if degraded is not None:
            return degraded
        servers = payload_rows(snap, "servers")
        if not servers:
            return _notice("no MCP servers declared in the readable configs", ctx)
        lines = [_server_line(server) for server in servers]
        return PaneBody(cursor_rows(lines, ctx), len(lines))


def _server_line(server: McpServer) -> str:
    """``cloud-hub   enabled   stdio   tools=not-measured   scopes=2``.

    ``tools=`` prints ``not-measured`` rather than ``0`` because this source performs no MCP
    handshake — an unmeasured tool count must never read as a health verdict.
    """
    tail = "" if server.last_error is None else f" · err={safe(server.last_error):.60}"
    return (
        f"[{safe(server.state)}] {safe(server.name):.36} · {safe(server.transport):.16} · "
        f"tools={measured(server.tool_count)} · scopes={len(server.declared_in)}{tail}"
    )


#: The default tab strip, in switch-key order (``1``-``5``).
PANES: tuple[Pane, ...] = (
    CodexPane(),
    AgentsPane(),
    WorkflowsPane(),
    DatabricksPane(),
    McpPane(),
)
