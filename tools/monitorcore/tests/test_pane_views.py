"""Tests for ``monitorcore.pane_views`` — the five concrete panes, 100% line+branch.

Every pane is driven from a FIXTURE snapshot built in-process: no source is polled, no file
is read, no socket is opened and no terminal is bound. Three properties are asserted for
each pane: it renders its source's rows, it degrades to an explicit *not measured* row when
the source is absent or unreachable (never a fabricated zero), and a hostile name cannot put
an escape byte into the rows it emits.
"""

from __future__ import annotations

import pytest

from monitorcore.agents_source import AgentRow, AgentsPayload
from monitorcore.codex_source import CodexPayload
from monitorcore.codex_tail import CodexThread, fmt_dur
from monitorcore.contract import Snapshot, SourceState
from monitorcore.databricks_source import DbxPayload, DbxUnit, Liveness
from monitorcore.mcp_source import McpPayload, McpServer
from monitorcore.pane import NOT_MEASURED, Pane, PaneCtx
from monitorcore.pane_views import (
    PANES,
    NOT_MEASURED_SHORT,
    AgentsPane,
    CodexPane,
    DatabricksPane,
    McpPane,
    WorkflowsPane,
    age_label,
    measured,
)

NOW = 1_784_283_000.0
HOSTILE = "ev\x1b[2Jil\x07\x9bx"
CTX = PaneCtx(cols=120, now=NOW)


def _snap(
    payload: object, *, reachable: bool = True, error: str | None = None
) -> Snapshot[object]:
    return Snapshot(
        source_id="src",
        ts=NOW,
        reachable=reachable,
        stale=not reachable,
        state=SourceState.IDLE if reachable else SourceState.UNREACHABLE,
        headline="h",
        payload=payload,
        age_s=None,
        error=error,
    )


def _agent(**kw: object) -> AgentRow:
    base: dict[str, object] = {
        "name": "scout",
        "agent_type": "general-purpose",
        "desc": "",
        "wf": "",
        "bucket": "idle",
        "age_s": 5.0,
        "running": False,
        "size": 1,
        "last": "reading",
        "path": "p",
    }
    base.update(kw)
    return AgentRow(**base)


def _thread(key: str = "t1") -> CodexThread:
    th = CodexThread(key=key, source="stream", path="p", label="lane")
    th.status = "idle"
    th.last_ts = NOW
    return th


def _text(pane: Pane, snap: Snapshot[object] | None, ctx: PaneCtx = CTX) -> str:
    return "\n".join(pane.body(snap, ctx).lines)


# ───────────────────────────── helpers ─────────────────────────────
@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (-3.0, "00:00"),
        (0.0, "00:00"),
        (42.0, "00:42"),
        (600.0, "10:00"),
        (7200.0, "2:00:00"),
    ],
)
def test_age_label_covers_every_band(seconds: float, expected: str):
    assert age_label(seconds) == expected


def test_age_label_is_the_EXISTING_house_duration_format_not_a_third_one():
    """One board, one spelling: the codex pane already paints ``fmt_dur``."""
    assert age_label(90.0) == fmt_dur(90.0)


def test_age_label_clamps_clock_skew_instead_of_printing_unknown():
    """``fmt_dur`` reserves ``--:--`` for "not measured"; a negative age IS measured."""
    assert age_label(-3.0) == "00:00" and fmt_dur(-3.0) == "--:--"


def test_measured_prints_not_measured_for_none_and_the_value_otherwise():
    assert measured(None) == NOT_MEASURED_SHORT
    assert measured(3) == "3"


# ───────────────────────────── the shared degradation contract ─────────────────────────────
@pytest.mark.parametrize("pane", list(PANES), ids=[p.id for p in PANES])
def test_every_pane_says_not_measured_when_its_source_is_unregistered(pane: Pane):
    body = pane.body(None, CTX)
    assert body.count == 0
    assert NOT_MEASURED in "\n".join(body.lines)
    assert "no source registered" in "\n".join(body.lines)


@pytest.mark.parametrize("pane", list(PANES), ids=[p.id for p in PANES])
def test_every_pane_says_not_measured_when_its_source_is_unreachable(pane: Pane):
    body = pane.body(_snap(None, reachable=False, error="creds missing"), CTX)
    assert body.count == 0
    joined = "\n".join(body.lines)
    assert NOT_MEASURED in joined and "creds missing" in joined
    assert " 0 " not in joined  # never a fabricated zero


@pytest.mark.parametrize("pane", list(PANES), ids=[p.id for p in PANES])
def test_every_pane_falls_back_to_a_generic_reason_without_an_error_string(pane: Pane):
    body = pane.body(_snap(None, reachable=False), CTX)
    assert "source unreachable" in "\n".join(body.lines)


@pytest.mark.parametrize("pane", list(PANES), ids=[p.id for p in PANES])
def test_every_pane_declares_a_source_and_a_distinct_title(pane: Pane):
    assert isinstance(pane, Pane)
    assert pane.source_id and pane.title


def test_the_default_tab_strip_has_five_unique_panes():
    assert len(PANES) == 5
    assert len({p.id for p in PANES}) == 5


# ───────────────────────────── codex pane ─────────────────────────────
def test_codex_pane_reuses_the_phase_one_renderer():
    body = CodexPane().body(_snap(CodexPayload(threads=(_thread(),))), CTX)
    assert body.count == 2  # one group header + one thread row
    assert any("lane" in line for line in body.lines)


def test_codex_pane_with_no_threads_reports_a_measured_empty_not_an_unmeasured_one():
    body = CodexPane().body(_snap(CodexPayload()), CTX)
    assert body.count == 0
    assert "no codex threads in the window" in "\n".join(body.lines)
    assert NOT_MEASURED not in "\n".join(body.lines)


def test_codex_pane_honours_the_cursor_and_the_selection():
    payload = CodexPayload(threads=(_thread("a"), _thread("b")))
    selected = CodexPane().body(_snap(payload), PaneCtx(cols=120, now=NOW, selected=1))
    readonly = CodexPane().body(
        _snap(payload), PaneCtx(cols=120, now=NOW, selected=1, cursor=False)
    )
    assert any(line.startswith("> ") for line in selected.lines)
    assert not any(line.startswith("> ") for line in readonly.lines)


def test_codex_pane_clamps_an_out_of_range_selection():
    body = CodexPane().body(
        _snap(CodexPayload(threads=(_thread(),))),
        PaneCtx(cols=120, now=NOW, selected=99),
    )
    assert sum(line.startswith("> ") for line in body.lines) == 1


# ───────────────────────────── agents pane ─────────────────────────────
def test_agents_pane_lists_one_row_per_transcript():
    body = AgentsPane().body(
        _snap(AgentsPayload(rows=(_agent(name="alpha"), _agent(name="beta")))), CTX
    )
    assert body.count == 2
    assert "alpha" in body.lines[0] and "beta" in body.lines[1]


def test_agents_pane_with_no_rows_reports_a_measured_empty():
    body = AgentsPane().body(_snap(AgentsPayload()), CTX)
    assert body.count == 0
    assert "no subagent transcripts observed" in "\n".join(body.lines)


def test_agents_pane_uses_ascii_glyphs_on_a_narrow_terminal():
    payload = AgentsPayload(rows=(_agent(bucket="running"),))
    wide = _text(AgentsPane(), _snap(payload), PaneCtx(cols=160, now=NOW))
    narrow = _text(AgentsPane(), _snap(payload), PaneCtx(cols=48, now=NOW))
    assert "▶" in wide
    assert "▶" not in narrow and ">" in narrow


def test_agents_pane_renders_a_dash_for_a_flat_task_agent_and_the_id_otherwise():
    flat = _text(AgentsPane(), _snap(AgentsPayload(rows=(_agent(wf=""),))))
    owned = _text(AgentsPane(), _snap(AgentsPayload(rows=(_agent(wf="wf_9"),))))
    assert "· - ·" in flat
    assert "wf_9" in owned


def test_agents_pane_falls_back_to_a_question_mark_for_an_unknown_bucket():
    text = _text(AgentsPane(), _snap(AgentsPayload(rows=(_agent(bucket="mystery"),))))
    assert "? [MYSTERY]" in text


# ───────────────────────────── workflows pane ─────────────────────────────
def test_workflows_pane_rolls_agents_up_by_owning_workflow():
    rows = (
        _agent(name="a", wf="wf_1", bucket="running", age_s=9.0),
        _agent(name="b", wf="wf_1", bucket="idle", age_s=3.0),
        _agent(name="c", wf="", bucket="idle", age_s=1.0),
    )
    body = WorkflowsPane().body(_snap(AgentsPayload(rows=rows)), CTX)
    assert body.count == 2
    joined = "\n".join(body.lines)
    assert "wf_1" in joined and "(no workflow)" in joined
    assert "2 agents" in joined
    assert "00:03" in joined  # the newest member drives the workflow age


def test_workflows_pane_says_done_is_NOT_MEASURED_rather_than_implying_zero():
    """Without the per-workflow journal port, a FINISHED and a HUNG workflow look alike.

    ``agents_source`` passes ``journal_state=None``, so no row can ever bucket ``done``.
    Printing ``0 done`` — or omitting it — would let a completed workflow read as a hang on
    the board built to spot hangs, so the missing signal is named on every row.
    """
    rows = (_agent(name="a", wf="wf_1", bucket="idle", age_s=11000.0),)
    joined = "\n".join(WorkflowsPane().body(_snap(AgentsPayload(rows=rows)), CTX).lines)
    assert f"done={NOT_MEASURED_SHORT}" in joined
    assert "0 done" not in joined


def test_workflows_pane_marks_a_workflow_with_a_failed_agent():
    rows = (_agent(wf="wf_1", bucket="error"), _agent(wf="wf_1", bucket="running"))
    text = _text(WorkflowsPane(), _snap(AgentsPayload(rows=rows)))
    assert "✖" in text and "1 error" in text


def test_workflows_pane_marks_a_quiet_workflow_idle():
    text = _text(WorkflowsPane(), _snap(AgentsPayload(rows=(_agent(wf="wf_1"),))))
    assert "·" in text


def test_workflows_pane_with_no_rows_reports_a_measured_empty():
    body = WorkflowsPane().body(_snap(AgentsPayload()), CTX)
    assert body.count == 0
    assert "no workflow-owned agents observed" in "\n".join(body.lines)


# ───────────────────────────── databricks pane ─────────────────────────────
def test_databricks_pane_lists_units_with_the_sources_own_busy_glyph():
    units = (
        DbxUnit(
            unit_id="u-1",
            run_id="r-1",
            liveness=Liveness.THINKING,
            busy=True,
            idle_s=8.0,
        ),
        DbxUnit(
            unit_id="u-2",
            run_id="r-1",
            liveness=Liveness.QUEUED,
            busy=False,
            idle_s=90.0,
        ),
    )
    body = DatabricksPane().body(_snap(DbxPayload(units=units)), CTX)
    assert body.count == 2
    assert "u-1" in body.lines[0] and "idle=00:08" in body.lines[0]
    assert body.lines[0][2] != body.lines[1][2]  # busy vs idle glyph differ


def test_databricks_pane_appends_a_unit_error_when_there_is_one():
    units = (DbxUnit(unit_id="u-1", error="OOM killed"),)
    assert "OOM killed" in _text(DatabricksPane(), _snap(DbxPayload(units=units)))


def test_databricks_pane_with_no_units_reports_a_measured_empty_not_not_measured():
    body = DatabricksPane().body(_snap(DbxPayload()), CTX)
    assert body.count == 0
    joined = "\n".join(body.lines)
    assert "no units observed in the event stream" in joined
    assert NOT_MEASURED not in joined


# ───────────────────────────── mcp pane ─────────────────────────────
def test_mcp_pane_prints_unmeasured_health_never_a_zero_tool_count():
    servers = (
        McpServer(
            name="cloud-hub",
            declared_in=("user",),
            state="enabled",
            transport="stdio",
        ),
    )
    body = McpPane().body(_snap(McpPayload(servers=servers)), CTX)
    assert body.count == 1
    row = body.lines[0]
    assert f"tools={NOT_MEASURED_SHORT}" in row
    assert "tools=0" not in row
    assert "enabled" in row and "scopes=1" in row


def test_mcp_pane_prints_the_resolved_state_and_keeps_a_disagreement_as_a_note():
    servers = (
        McpServer(
            name="markitdown",
            declared_in=("~/.claude.json",),
            disabled_in=("~/.claude/settings.json",),
            state="denied",
            notes=("approved in enabledMcpjsonServers but suppressed by settings",),
        ),
    )
    row = McpPane().body(_snap(McpPayload(servers=servers)), CTX).lines[0]
    assert "[denied]" in row and "note=approved in" in row


def test_mcp_pane_names_every_config_document_it_could_not_parse():
    """A corrupt document used to drop its servers with the parse error rendered NOWHERE."""
    body = McpPane().body(
        _snap(
            McpPayload(
                servers=(McpServer(name="kept", state="enabled"),),
                problems=("~/.claude.json: unparsable json: line 1",),
                docs_attempted=2,
            )
        ),
        CTX,
    )
    joined = "\n".join(body.lines)
    assert "mcp config" in joined and NOT_MEASURED in joined
    assert "unparsable json" in joined
    assert "kept" in joined  # the readable scope is still listed


def test_mcp_pane_reports_an_unreadable_document_even_with_zero_servers():
    """Otherwise "one config is corrupt" renders identically to "nothing is declared"."""
    corrupt = McpPane().body(
        _snap(
            McpPayload(problems=("~/.claude.json: unparsable json",), docs_attempted=1)
        ),
        CTX,
    )
    empty = McpPane().body(_snap(McpPayload(docs_attempted=1)), CTX)
    assert "unparsable json" in "\n".join(corrupt.lines)
    assert corrupt.lines != empty.lines
    assert "no MCP servers declared" in "\n".join(empty.lines)


def test_mcp_pane_shows_a_measured_error_when_one_is_supplied():
    servers = (McpServer(name="a", last_error="handshake refused"),)
    assert "err=handshake refused" in _text(
        McpPane(), _snap(McpPayload(servers=servers))
    )


def test_mcp_pane_with_no_declarations_reports_a_measured_empty():
    body = McpPane().body(_snap(McpPayload()), CTX)
    assert body.count == 0
    assert "no MCP servers declared" in "\n".join(body.lines)


# ───────────────────────────── escape injection (E-1) ─────────────────────────────
@pytest.mark.parametrize(
    ("pane", "payload"),
    [
        (CodexPane(), CodexPayload(threads=(_thread(HOSTILE),))),
        (
            AgentsPane(),
            AgentsPayload(rows=(_agent(name=HOSTILE, wf=HOSTILE, last=HOSTILE),)),
        ),
        (WorkflowsPane(), AgentsPayload(rows=(_agent(wf=HOSTILE),))),
        (
            DatabricksPane(),
            DbxPayload(units=(DbxUnit(unit_id=HOSTILE, error=HOSTILE),)),
        ),
        (McpPane(), McpPayload(servers=(McpServer(name=HOSTILE, last_error=HOSTILE),))),
    ],
    ids=["codex", "agents", "workflows", "databricks", "mcp"],
)
def test_a_hostile_name_cannot_emit_an_escape_byte_into_a_pane(
    pane: Pane, payload: object
):
    joined = "\n".join(pane.body(_snap(payload), CTX).lines)
    assert not any(ch in joined for ch in ("\x1b", "\x07", "\x9b", "\x00"))


def test_a_hostile_error_string_cannot_escape_the_degraded_row():
    joined = "\n".join(
        McpPane().body(_snap(None, reachable=False, error=HOSTILE), CTX).lines
    )
    assert not any(ch in joined for ch in ("\x1b", "\x07", "\x9b"))


def test_barrier_one_alone_defangs_the_row_even_with_the_last_mile_neutered(
    monkeypatch: pytest.MonkeyPatch,
):
    """With ``clip`` replaced by identity, the INGEST strip must still be sufficient."""
    monkeypatch.setattr("monitorcore.pane.clip", lambda text, _width: text)
    rows = (_agent(name=HOSTILE, wf=HOSTILE, last=HOSTILE),)
    joined = "\n".join(AgentsPane().body(_snap(AgentsPayload(rows=rows)), CTX).lines)
    assert HOSTILE not in joined
    assert not any(ch in joined for ch in ("\x1b", "\x07", "\x9b"))
