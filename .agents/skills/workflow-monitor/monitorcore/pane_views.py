"""``pane_views`` — the five concrete cockpit panes, each a THIN adapter over one source.

Every pane here is deliberately small: it reads an ALREADY-POLLED snapshot, formats rows and
hands them back. No pane opens a file, a socket or a clock — the reuse rule is absolute:

===============  ====================================================================
pane             the existing source it renders
===============  ====================================================================
``codex``        :class:`monitorcore.codex_source.CodexSource` → re-uses the WHOLE Phase-1
                 renderer (:func:`monitorcore.group_tree.derive_groups` +
                 :func:`monitorcore.view.render_view`) INCLUDING its WU6 stall overlay, so
                 the drill view is not forked and no signal is quietly dropped.
``agents``       :class:`monitorcore.agents_source.AgentsSource` (which is itself a wrapper
                 over :func:`monitorcore.discovery.scan` — no second transcript walk).
``workflows``    the SAME ``agents`` snapshot, re-projected by workflow id. One poll, two
                 panes: a workflow row is a rollup of the agents that workflow owns, and it
                 says ``done=not-measured`` because the per-workflow journal read that
                 could separate FINISHED from HUNG is a port this package does not carry.
``databricks``   :class:`monitorcore.databricks_source.DatabricksSource`, re-using its
                 measured :func:`~monitorcore.databricks_source.busy_glyph`.
``mcp``          :class:`monitorcore.mcp_source.McpSource` — inventory only; every health
                 column prints ``not-measured`` and every unreadable config is named.
``health``       :class:`monitorcore.health_source.SystemHealthSource` — the sentinel sample.
                 A SCALAR payload, so it degrades through
                 :func:`monitorcore.pane.payload_of` rather than ``payload_rows``, and it
                 leads with an explicit STALE row when the dead-man window has expired.
===============  ====================================================================

Degradation is uniform and explicit. A pane whose source is **not registered** or **not
reachable** renders a single :func:`monitorcore.pane.not_measured` row and reports ZERO
selectable rows — it never fabricates an empty list that would read as "healthy and idle".
A source that WAS reached and legitimately holds nothing renders a separate "nothing
observed" notice, because a measured zero and an unmeasured field are different facts.

That split is only as good as the sources' own reachability flag, so the two adapters that
could previously read an ABSENT artifact as an empty one now report it unreachable (a
missing Databricks event file, a missing subagents directory). A pane cannot infer it: from
here, "the file was not there" and "the file was empty" are the same empty tuple.

Glyphs follow the existing width policy (:func:`monitorcore.responsive.layout_for`), so a
narrow terminal degrades to ASCII exactly as the Phase-1 board does. Pure over its inputs.
"""

from __future__ import annotations

from dataclasses import replace

from .agents_source import AgentRow, AgentsSource, workflow_key
from .codex_source import CodexSource
from .codex_tail import CodexThread, fmt_dur
from .contract import Snapshot
from .databricks_source import DatabricksSource, DbxUnit, busy_glyph
from .group_tree import derive_groups
from .health_source import HealthPayload, SystemHealthSource
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
    payload_of,
    payload_rows,
    safe,
    snap_is_stale,
)
from .responsive import layout_for
from .view import render_view

__all__ = [
    "PANES",
    "AgentsPane",
    "CodexPane",
    "DatabricksPane",
    "HealthPane",
    "McpPane",
    "WorkflowsPane",
    "age_label",
    "measured",
]

#: ``done`` is currently UNREACHABLE for both agent panes — see the ``agents_source``
#: honesty limits: the source passes ``journal_state=None``, so ``bucket_agent`` can only
#: return ``running`` / ``idle`` / ``error``. The entry is kept (not deleted) because the
#: bucket vocabulary is ``bucket_agent``'s, not this module's: wiring the per-workflow
#: journal port later must not also have to remember to re-add a glyph.
_GLYPHS = {"running": "▶", "idle": "·", "done": "✔", "error": "✖"}
_ASCII_GLYPHS = {"running": ">", "idle": ".", "done": "+", "error": "x"}
_UNKNOWN_GLYPH = "?"

#: What an unmeasured scalar prints as. Never ``0``, never blank — see ``pane`` invariant 2.
NOT_MEASURED_SHORT = "not-measured"


def age_label(seconds: float) -> str:
    """A duration for the board, in the EXISTING house format (``MM:SS`` / ``H:MM:SS``).

    Delegates to :func:`monitorcore.codex_tail.fmt_dur`, the formatter the Phase-1 codex
    board already paints, so one board no longer shows three spellings of the same concept
    (``00:00`` on the codex pane, ``12s`` on agents, ``idle=7m`` on databricks). A negative
    value is clock skew, not an age, and clamps to zero rather than printing ``--:--``,
    which ``fmt_dur`` reserves for "unknown".
    """
    return fmt_dur(max(0.0, seconds))


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
    """The Phase-1 Codex drill view, unchanged — this pane only routes to it.

    "Unchanged" includes the WU6 stall layer: ``ctx.marks`` is forwarded to
    :func:`monitorcore.view.render_view` exactly as
    :func:`monitorcore.cockpit.run_interactive` forwards
    :func:`monitorcore.cockpit.stall_marks`, so a ``[STALL]`` / ``[BLOCKED]`` inference is
    painted on this board too. Dropping ``marks=`` here silently deleted the one signal the
    monitor exists for; the board owns the tracker because a freeze needs TWO polls.
    """

    id: str = PaneId.CODEX
    title: str = "codex"
    source_id: str = CodexSource.id

    def body(self, snap: Snapshot[object] | None, ctx: PaneCtx) -> PaneBody:
        degraded = _degraded("codex threads", snap, ctx)
        if degraded is not None:
            return degraded
        threads = payload_rows(snap, "threads", of=CodexThread)
        if not threads:
            return _notice("no codex threads in the window", ctx)
        groups = derive_groups(threads)
        count = len(nav_items(visible_groups(groups, ViewState())))
        state = ViewState(selected=clamp(ctx.selected, count))
        lines = render_view(
            groups, state, ctx.now, ctx.cols, cursor=ctx.cursor, marks=ctx.marks
        )
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
        rows = payload_rows(snap, "rows", of=AgentRow)
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
    """A rollup of the SAME agents snapshot, one row per owning workflow.

    The same question ``wfmon_export/model.py``'s ``_rollup`` answers, over the ONE poll the
    agents pane already made — but with a strictly smaller input: that rollup is fed by
    ``workflow_run.journal_states`` (one ``journal.jsonl`` per workflow), a port this
    package does not carry, so ``done`` is genuinely unmeasured here rather than zero.
    """

    id: str = PaneId.WORKFLOWS
    title: str = "workflows"
    source_id: str = AgentsSource.id

    def body(self, snap: Snapshot[object] | None, ctx: PaneCtx) -> PaneBody:
        degraded = _degraded("workflows", snap, ctx)
        if degraded is not None:
            return degraded
        rows = payload_rows(snap, "rows", of=AgentRow)
        if not rows:
            return _notice("no workflow-owned agents observed", ctx)
        buckets: dict[str, list[AgentRow]] = {}
        for row in rows:
            buckets.setdefault(workflow_key(row), []).append(row)
        glyphs = _glyphs(ctx.cols)
        lines = [_workflow_line(key, buckets[key], glyphs) for key in sorted(buckets)]
        return PaneBody(cursor_rows(lines, ctx), len(lines))


def _workflow_line(key: str, members: list[AgentRow], glyphs: dict[str, str]) -> str:
    """``▶ wf_bfc00235 · 6 agents · 2 running · 0 error · done=not-measured · 00:12 idle``.

    ``done=`` is spelled out rather than omitted or printed as ``0``. Without the
    per-workflow journal read (see :class:`WorkflowsPane`), a FINISHED workflow and a HUNG
    one both present as zero running agents — and this is the board built to spot hangs, so
    the missing signal has to be visible, not implied away.
    """
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
        f"{running} running · {errors} error · done={NOT_MEASURED_SHORT} · "
        f"{age_label(newest)} idle"
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
        units = payload_rows(snap, "units", of=DbxUnit)
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
    """The declared MCP inventory. Health columns print ``not-measured``, never ``0``.

    A config document that was FOUND but could not be parsed gets its own explicit
    not-measured row, ahead of the inventory. Without it a corrupt ``~/.claude.json`` simply
    dropped its 66 servers and the pane rendered a confident, much smaller list — the parse
    error was captured in the payload and displayed nowhere.
    """

    id: str = PaneId.MCP
    title: str = "mcp"
    source_id: str = McpSource.id

    def body(self, snap: Snapshot[object] | None, ctx: PaneCtx) -> PaneBody:
        degraded = _degraded("mcp inventory", snap, ctx)
        if degraded is not None:
            return degraded
        problems = [
            not_measured("mcp config", str(p))
            for p in payload_rows(snap, "problems", of=str)
        ]
        servers = payload_rows(snap, "servers", of=McpServer)
        if not servers:
            if problems:
                return PaneBody(cursor_rows(problems, ctx), len(problems))
            return _notice("no MCP servers declared in the readable configs", ctx)
        lines = problems + [_server_line(server) for server in servers]
        return PaneBody(cursor_rows(lines, ctx), len(lines))


def _server_line(server: McpServer) -> str:
    """``cloud-hub   enabled   stdio   tools=not-measured   scopes=2``.

    ``tools=`` prints ``not-measured`` rather than ``0`` because this source performs no MCP
    handshake — an unmeasured tool count must never read as a health verdict. ``state`` is
    the resolved verdict (``enabled`` / ``disabled`` / ``denied`` / ``pending-approval`` /
    ``undefined``); a scope DISAGREEMENT rides in ``note=``, never in the state.
    """
    tail = "" if server.last_error is None else f" · err={safe(server.last_error):.60}"
    if server.notes:
        tail += f" · note={safe(server.notes[0]):.60}"
    return (
        f"[{safe(server.state)}] {safe(server.name):.36} · {safe(server.transport):.16} · "
        f"tools={measured(server.tool_count)} · scopes={len(server.declared_in)}{tail}"
    )


class HealthPane:
    """Workstation liveness — the sentinel sample, as a row set instead of an orphan.

    :class:`~monitorcore.health_source.SystemHealthSource` was written, unit-tested and then
    wired to NOTHING: before this pane existed it appeared in no ``PaneId``, no ``PANES`` entry
    and no :func:`monitorcore.unified.default_sources` call, so the one adapter whose entire
    purpose is to notice that the observer has died was itself unobservable. Measured with a
    positive control: ``SystemHealthSource`` matched zero other modules in the package while
    ``McpSource`` matched four.

    THE STALE ROW IS THE POINT. The sentinel's last sample stays readable forever after the
    sentinel dies, so a pane that simply printed the numbers would render a healthy board for a
    machine nobody is watching. When the source flags the snapshot stale (its dead-man window,
    :class:`~monitorcore.health_source.SystemHealthSource`) the first row says so, ahead of any
    figure, and every figure below it is explicitly labelled as the last-good reading rather
    than a current one.

    The payload is ONE sample, not a row sequence, so the never-raise guarantee comes from
    :func:`monitorcore.pane.payload_of` rather than ``payload_rows``.
    """

    id: str = PaneId.HEALTH
    title: str = "health"
    source_id: str = SystemHealthSource.id

    def body(self, snap: Snapshot[object] | None, ctx: PaneCtx) -> PaneBody:
        degraded = _degraded("workstation health", snap, ctx)
        if degraded is not None:
            return degraded
        sample = payload_of(snap, HealthPayload)
        if sample is None:
            return _notice(
                not_measured("workstation health", "payload is not a sentinel sample"),
                ctx,
            )
        lines = _health_lines(sample, stale=snap_is_stale(snap))
        return PaneBody(cursor_rows(lines, ctx), len(lines))


def _health_lines(p: HealthPayload, *, stale: bool) -> list[str]:
    """``[GREEN] phys 41% · commit 57% · driver none`` and the supporting counts.

    ``gdi_max`` / ``usr_max`` print :data:`NOT_MEASURED_SHORT` when the sentinel did not supply
    them — the source models them ``int | None`` precisely because a GUI-object count of zero is
    a different fact from an unsampled one, and this is the board that exists to tell those two
    apart.
    """
    lines: list[str] = []
    if stale:
        lines.append(
            "[STALE] retained last-good sample — the sentinel feed is not advancing; "
            "every figure below is the LAST reading, not a current one"
        )
    lines.append(
        f"[{safe(p.band).upper()}] phys {p.phys_pct:.0f}% · commit {p.commit_pct:.0f}% · "
        f"driver {safe(p.driver) or 'none'}"
    )
    lines.append(f"procs {p.procs} · handles {p.handles} · threads {p.threads}")
    lines.append(
        f"gdi_max {measured(p.gdi_max)} · usr_max {measured(p.usr_max)} · "
        f"top {safe(p.gdi_max_proc) or NOT_MEASURED_SHORT}"
    )
    lines.append(f"orphaned MCP runtimes {p.orphan_count}")
    lines.extend(f"  orphan · {safe(o)}" for o in p.orphan_top)
    return lines


#: The default tab strip, in switch-key order (``1``-``6``).
PANES: tuple[Pane, ...] = (
    CodexPane(),
    AgentsPane(),
    WorkflowsPane(),
    DatabricksPane(),
    McpPane(),
    HealthPane(),
)
