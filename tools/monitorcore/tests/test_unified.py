"""Tests for ``monitorcore.unified`` — the switchable-pane board + CLI, 100% line+branch.

The whole board is driven through injected seams (fake sources, a scripted ``read_key``, a
recording ``write``/``out``, a pinned clock, an injected ``supported_fn``), so no real
terminal, keypress, source, socket or wall clock is touched. Two properties get dedicated
end-to-end coverage:

* **pane switching** — each of the five panes renders from a FIXTURE snapshot through the
  real ``--once`` CLI path, with no network and no live source;
* **escape injection** — a hostile agent / workflow / MCP / Databricks / Codex name cannot
  put an ESC byte into the frame, asserted both on the logical rows AND on the exact byte
  count of the painted ``ansi_screen.render_frame`` output.
"""

from __future__ import annotations

import pytest

from monitorcore.agents_source import AgentRow, AgentsPayload, AgentsSource
from monitorcore.ansi_screen import render_frame
from monitorcore.codex_source import CodexPayload, CodexSource
from monitorcore.codex_tail import CodexThread, ToolEvent
from monitorcore.contract import MonitorSource, Snapshot, SourceState
from monitorcore.databricks_source import DatabricksSource, DbxPayload, DbxUnit
from monitorcore.health_source import HealthPayload, SystemHealthSource
from monitorcore.mcp_source import McpPayload, McpServer, McpSource
from monitorcore.pane import NOT_MEASURED, PaneId
from monitorcore.pane_views import PANES
from monitorcore.stall import StallTracker
from monitorcore.unified import (
    BoardFrame,
    BoardState,
    _build_parser,
    _digit_pane,
    active_pane,
    apply_key,
    codex_marks,
    default_sources,
    frame,
    main,
    poll_all,
    run_board,
)

NOW = 1_784_283_000.0
HOSTILE = "ev\x1b[2Jil\x07\x9b0m"
PANE_IDS = [p.id for p in PANES]


def _snap(source_id: str, payload: object) -> Snapshot[object]:
    return Snapshot(
        source_id=source_id,
        ts=NOW,
        reachable=True,
        stale=False,
        state=SourceState.IDLE,
        headline=f"{source_id} headline",
        payload=payload,
        age_s=3.0,
        error=None,
    )


class _FakeSource:
    """A minimal ``MonitorSource``-shaped stub: only ``poll`` is exercised by the board."""

    def __init__(self, source_id: str, payload: object) -> None:
        self.id = source_id
        self._snap = _snap(source_id, payload)
        self.polls = 0

    def poll(self) -> Snapshot[object]:
        self.polls += 1
        return self._snap


class _RudeSource:
    """A rogue adapter that violates the ``poll`` contract by raising."""

    id = "rude"

    def poll(self) -> Snapshot[object]:
        raise RuntimeError("kaboom\x1b[2J")


def _thread(key: str = "t1") -> CodexThread:
    th = CodexThread(key=key, source="stream", path="p", label="lane")
    th.status = "idle"
    th.last_ts = NOW
    return th


def _agent(**kw: object) -> AgentRow:
    base: dict[str, object] = {
        "name": "scout",
        "agent_type": "general-purpose",
        "desc": "",
        "wf": "wf_1",
        "bucket": "running",
        "age_s": 4.0,
        "running": True,
        "size": 1,
        "last": "reading",
        "path": "p",
    }
    base.update(kw)
    return AgentRow(**base)


def _fixture_sources(*, hostile: bool = False) -> dict[str, MonitorSource[object]]:
    """One fixture snapshot per registered source — no I/O, no network, no live poll."""
    name = HOSTILE if hostile else "friendly"
    return {
        CodexSource.id: _FakeSource(
            CodexSource.id, CodexPayload(threads=(_thread(name),))
        ),
        AgentsSource.id: _FakeSource(
            AgentsSource.id,
            AgentsPayload(rows=(_agent(name=name, wf=name, last=name),)),
        ),
        DatabricksSource.id: _FakeSource(
            DatabricksSource.id,
            DbxPayload(units=(DbxUnit(unit_id=name, run_id="r-1", error=name),)),
        ),
        McpSource.id: _FakeSource(
            McpSource.id,
            McpPayload(servers=(McpServer(name=name, declared_in=("user",)),)),
        ),
        SystemHealthSource.id: _FakeSource(
            SystemHealthSource.id,
            HealthPayload(band="green", driver=name, gdi_max_proc=name),
        ),
    }


def _blocked_thread(key: str = "t1") -> CodexThread:
    """An IDLE thread whose newest event is still ``running`` — WU6's BLOCKED shape."""
    th = CodexThread(key=key, source="stream", path="p", label="lane")
    th.status = "idle"
    th.last_ts = NOW - 500.0
    th.add_event(ToolEvent("cmd", "command", "sleep", "running", None, NOW - 500.0))
    return th


def _codex_only(thread: CodexThread) -> dict[str, MonitorSource[object]]:
    return {
        CodexSource.id: _FakeSource(CodexSource.id, CodexPayload(threads=(thread,)))
    }


# ───────────────────────────── active_pane ─────────────────────────────
def test_active_pane_resolves_by_id():
    assert active_pane(PANES, PaneId.MCP).id == PaneId.MCP


def test_active_pane_falls_back_to_the_first_pane_on_an_unknown_id():
    assert active_pane(PANES, "nope").id == PANES[0].id


# ───────────────────────────── poll_all ─────────────────────────────
def test_poll_all_polls_every_registered_source_once():
    sources = _fixture_sources()
    snaps = poll_all(sources, clock=lambda: NOW)
    assert set(snaps) == set(sources)
    assert all(s.polls == 1 for s in sources.values())  # pyright: ignore[reportAttributeAccessIssue]


def test_poll_all_converts_a_rogue_raising_adapter_into_an_unreachable_snapshot():
    snaps = poll_all({"rude": _RudeSource()}, clock=lambda: NOW)
    snap = snaps["rude"]
    assert snap.reachable is False and snap.stale is True
    assert snap.state is SourceState.UNREACHABLE
    assert snap.payload is None
    assert snap.error is not None and "\x1b" not in snap.error
    assert "\x1b" not in snap.headline


def test_a_rogue_source_degrades_only_its_own_pane():
    sources = dict(_fixture_sources())
    sources[McpSource.id] = _RudeSource()
    snaps = poll_all(sources, clock=lambda: NOW)
    mcp = frame(BoardState(pane=PaneId.MCP), snaps=snaps, cols=120, now=NOW)
    agents = frame(BoardState(pane=PaneId.AGENTS), snaps=snaps, cols=120, now=NOW)
    assert NOT_MEASURED in "\n".join(mcp.lines)
    assert "friendly" in "\n".join(agents.lines)


# ───────────────────────────── frame ─────────────────────────────
def test_frame_composes_the_tab_strip_the_badge_and_the_pane_body():
    rendered = frame(
        BoardState(pane=PaneId.AGENTS),
        snaps=poll_all(_fixture_sources(), clock=lambda: NOW),
        cols=120,
        now=NOW,
    )
    assert rendered.lines[0].startswith("panes ")
    assert "[2:agents]" in rendered.lines[0]
    assert "agents headline" in rendered.lines[1]
    assert "age=3s" in rendered.lines[1]
    assert rendered.count == 1
    assert "friendly" in rendered.lines[2]


def test_frame_for_an_unregistered_source_says_not_measured_and_still_renders():
    rendered = frame(BoardState(pane=PaneId.MCP), snaps={}, cols=120, now=NOW)
    joined = "\n".join(rendered.lines)
    assert rendered.count == 0
    assert joined.count(NOT_MEASURED) >= 2  # the badge AND the body both say it


def test_frame_without_a_cursor_is_the_read_only_once_form():
    snaps = poll_all(_fixture_sources(), clock=lambda: NOW)
    live = frame(BoardState(pane=PaneId.AGENTS), snaps=snaps, cols=120, now=NOW)
    once = frame(
        BoardState(pane=PaneId.AGENTS), snaps=snaps, cols=120, now=NOW, cursor=False
    )
    assert any(line.startswith("> ") for line in live.lines)
    assert not any(line.startswith("> ") for line in once.lines)


def test_board_frame_defaults():
    assert BoardFrame() == BoardFrame((), 0)
    assert BoardState() == BoardState(PaneId.CODEX, 0, False)


# ───────────────────────────── key handling ─────────────────────────────
@pytest.mark.parametrize("key", ["q", "quit"])
def test_quit_latches(key: str):
    assert apply_key(BoardState(), key).quit is True


def test_tab_cycles_forward_and_wraps():
    state = BoardState(pane=PANE_IDS[-1], selected=4)
    nxt = apply_key(state, "\t")
    assert nxt.pane == PANE_IDS[0]
    assert nxt.selected == 0  # a pane switch resets the cursor


def test_tab_from_an_unknown_pane_lands_on_the_second_pane():
    assert apply_key(BoardState(pane="ghost"), "tab").pane == PANE_IDS[1]


@pytest.mark.parametrize(("key", "expected"), [("1", PANE_IDS[0]), ("5", PANE_IDS[4])])
def test_a_digit_jumps_straight_to_its_pane(key: str, expected: str):
    assert apply_key(BoardState(pane=PANE_IDS[2]), key).pane == expected


@pytest.mark.parametrize("key", ["0", "9", "x", "up", "", "12"])
def test_digit_pane_rejects_everything_that_is_not_an_in_range_single_digit(key: str):
    assert _digit_pane(PANE_IDS, key) is None


@pytest.mark.parametrize("key", ["up", "k"])
def test_up_moves_the_cursor_and_clamps_at_the_top(key: str):
    assert apply_key(BoardState(selected=2), key, count=5).selected == 1
    assert apply_key(BoardState(selected=0), key, count=5).selected == 0


@pytest.mark.parametrize("key", ["down", "j"])
def test_down_moves_the_cursor_and_clamps_at_the_bottom(key: str):
    assert apply_key(BoardState(selected=2), key, count=5).selected == 3
    assert apply_key(BoardState(selected=4), key, count=5).selected == 4


def test_an_unmapped_key_is_a_no_op():
    state = BoardState(selected=1)
    assert apply_key(state, "Z", count=5) == state


def test_the_cursor_is_pinned_when_the_pane_has_nothing_selectable():
    assert apply_key(BoardState(), "down", count=0).selected == 0


# ───────────────────────────── run_board ─────────────────────────────
def test_run_board_repaints_per_keystroke_and_returns_on_quit():
    sources = _fixture_sources()
    painted: list[tuple[str, ...]] = []
    keys = iter(["3", "down", "q"])
    final = run_board(
        sources,
        read_key=lambda: next(keys),
        write=lambda rows: painted.append(tuple(rows)),
        clock=lambda: NOW,
        cols_fn=lambda: 100,
    )
    assert final.quit is True
    assert final.pane == PaneId.WORKFLOWS
    assert len(painted) == 3  # one repaint per keystroke — no busy poll
    assert all(rows[0].startswith("panes ") for rows in painted)
    # the third frame is already on the workflows pane
    assert "[3:workflows]" in painted[2][0]


def test_run_board_starts_from_an_injected_initial_state():
    keys = iter(["q"])
    final = run_board(
        _fixture_sources(),
        read_key=lambda: next(keys),
        write=lambda _rows: None,
        clock=lambda: NOW,
        initial=BoardState(pane=PaneId.MCP),
    )
    assert final.pane == PaneId.MCP


# ───────────────────────────── CLI ─────────────────────────────
@pytest.mark.parametrize("pane_id", PANE_IDS)
def test_once_renders_every_pane_from_a_fixture_with_no_live_source(pane_id: str):
    out: list[str] = []
    code = main(
        ["--once", "--pane", pane_id, "--width", "110"],
        sources=_fixture_sources(),
        out=out.append,
        clock=lambda: NOW,
        supported_fn=lambda: True,
    )
    assert code == 0
    assert out[0].startswith("panes ")
    assert f":{pane_id}]" in out[0]
    joined = "\n".join(out)
    assert (
        NOT_MEASURED not in joined
    )  # every pane's source WAS registered and reachable
    assert not any(line.startswith("> ") for line in out)  # --once is read-only
    assert all(len(line) <= 110 for line in out)


def test_a_non_interactive_terminal_degrades_to_the_single_frame():
    out: list[str] = []
    called: list[str] = []
    code = main(
        [],
        sources=_fixture_sources(),
        out=out.append,
        clock=lambda: NOW,
        board=lambda *_a, **_k: called.append("board") or BoardState(),
        supported_fn=lambda: False,
    )
    assert code == 0 and called == [] and out


def test_an_interactive_terminal_hands_off_to_the_board_loop():
    seen: dict[str, object] = {}

    def _board(sources, **kw):
        seen.update(kw)
        seen["sources"] = sources
        return BoardState()

    code = main(
        ["--pane", "mcp", "--width", "64"],
        sources=_fixture_sources(),
        out=lambda _line: None,
        clock=lambda: NOW,
        board=_board,
        supported_fn=lambda: True,
    )
    assert code == 0
    assert seen["initial"] == BoardState(pane="mcp")
    assert seen["cols_fn"]() == 64  # pyright: ignore[reportCallIssue]


def test_default_sources_registers_one_adapter_per_pane_source():
    args = _build_parser().parse_args([])
    sources = default_sources(args, clock=lambda: NOW)
    assert set(sources) == {
        CodexSource.id,
        AgentsSource.id,
        DatabricksSource.id,
        McpSource.id,
        SystemHealthSource.id,
    }
    assert all(isinstance(src, MonitorSource) for src in sources.values())
    # every pane's declared source_id is actually registered
    assert {p.source_id for p in PANES} <= set(sources)


def test_the_parser_exposes_the_pane_choice_and_the_source_overrides():
    args = _build_parser().parse_args(
        [
            "--pane",
            "databricks",
            "--subagents-dir",
            "/s",
            "--events-path",
            "/e",
            "--mcp-config",
            "/a",
            "--mcp-config",
            "/b",
        ]
    )
    assert args.pane == "databricks"
    assert args.subagents_dir == "/s" and args.events_path == "/e"
    assert args.mcp_config == ["/a", "/b"]


def test_the_parser_rejects_an_unknown_pane():
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--pane", "nope"])


# ───────────────────────────── escape injection, end to end ─────────────────────────────
@pytest.mark.parametrize("pane_id", PANE_IDS)
def test_a_hostile_name_cannot_reach_the_painted_frame(pane_id: str):
    out: list[str] = []
    main(
        ["--once", "--pane", pane_id],
        sources=_fixture_sources(hostile=True),
        out=out.append,
        clock=lambda: NOW,
        supported_fn=lambda: True,
    )
    joined = "\n".join(out)
    assert HOSTILE not in joined
    assert not any(ch in joined for ch in ("\x1b", "\x07", "\x9b", "\x00"))
    # and once painted, the ONLY escapes are ansi_screen's own chrome:
    # SYNC_BEGIN + HOME + one CLEAR_EOL per line + CLEAR_EOS + SYNC_END
    painted = render_frame(out)
    assert painted.count("\x1b") == 4 + len(out)


# ─────────────────── the WU6 stall layer reaches the codex PANE ───────────────────
STALE_MTIME = lambda _path: None  # noqa: E731 — an unreadable mtime is signal 1


def test_codex_marks_classifies_a_blocked_thread_through_the_EXISTING_classifier():
    snaps = poll_all(_codex_only(_blocked_thread()))
    marks = codex_marks(snaps, StallTracker(), NOW, stale_s=90.0, mtime_fn=STALE_MTIME)
    assert marks == {"t1": "BLOCKED"}


def test_codex_marks_is_empty_when_the_codex_source_is_not_registered():
    marks = codex_marks({}, StallTracker(), NOW, stale_s=90.0, mtime_fn=STALE_MTIME)
    assert marks == {}


def test_the_board_PAINTS_the_stall_marker_the_phase_1_cockpit_paints():
    """The regression: the codex pane imported the renderer but dropped ``marks=``.

    The marker is the one signal this monitor exists for, so an A/B against the Phase-1
    loop — identical source, identical seams — must agree.
    """
    painted: list[tuple[str, ...]] = []
    keys = iter(["q"])
    run_board(
        _codex_only(_blocked_thread()),
        read_key=lambda: next(keys),
        write=lambda rows: painted.append(tuple(rows)),
        clock=lambda: NOW,
        cols_fn=lambda: 200,
        mtime_fn=STALE_MTIME,
    )
    assert "[BLOCKED]" in "\n".join(painted[0])


def test_the_board_reuses_ONE_tracker_so_a_content_freeze_can_corroborate():
    """A per-frame tracker could never fire: a STALL needs TWO polls to corroborate.

    ``STALLED`` outranks ``BLOCKED``, and it is the only marker gated on the cross-poll
    signal — so this is what a throwaway tracker would silently downgrade.
    """
    tracker = StallTracker()
    snaps = poll_all(_codex_only(_blocked_thread()))
    first = codex_marks(snaps, tracker, NOW, stale_s=90.0, mtime_fn=STALE_MTIME)
    second = codex_marks(snaps, tracker, NOW, stale_s=90.0, mtime_fn=STALE_MTIME)
    assert first == {"t1": "BLOCKED"}  # only signal 1 (mtime) has spoken so far
    assert second == {"t1": "STALL"}  # the content freeze corroborates on poll 2


def test_a_single_once_frame_shows_no_stall_marker_because_it_cannot_corroborate():
    rendered = frame(
        BoardState(pane=PaneId.CODEX),
        snaps=poll_all(_codex_only(_blocked_thread())),
        cols=200,
        now=NOW,
        cursor=False,
    )
    joined = "\n".join(rendered.lines)
    assert "[IDLE]" in joined and "[BLOCKED]" not in joined


# ─────────────────── the board is the LAST MILE for a raw error ───────────────────
def test_the_board_never_paints_a_raw_credential_from_a_snapshot_error():
    """Adapters keep ``Snapshot.error`` unredacted for logs; the frame must not show it."""
    token = "sk-" + "d" * 24

    class _Leaky:
        id = DatabricksSource.id

        def poll(self) -> Snapshot[object]:
            return Snapshot(
                source_id=self.id,
                ts=NOW,
                reachable=False,
                stale=True,
                state=SourceState.UNREACHABLE,
                headline="dbx [unreachable]",
                payload=DbxPayload(),
                age_s=None,
                error=f"auth failed for {token} at C:/Users/someone/.dbxmon",
            )

    rendered = frame(
        BoardState(pane=PaneId.DATABRICKS),
        snaps=poll_all({DatabricksSource.id: _Leaky()}),
        cols=300,
        now=NOW,
        cursor=False,
    )
    joined = "\n".join(rendered.lines)
    assert token not in joined and "[REDACTED:api-key]" in joined
    assert "C:/Users/someone" not in joined


# ─────────────────── a mis-registered payload degrades ONE pane ───────────────────
@pytest.mark.parametrize("pane_id", PANE_IDS)
def test_a_wrong_typed_payload_row_degrades_instead_of_tearing_the_board_down(
    pane_id: str,
):
    """``rows=("oops",)`` used to reach ``row.bucket`` and kill the WHOLE board."""

    class _Bogus:
        threads = ("oops",)
        rows = ("oops",)
        units = ("oops",)
        servers = ("oops",)
        problems = (7,)

    snaps = {
        src_id: _snap(src_id, _Bogus())
        for src_id in (
            CodexSource.id,
            AgentsSource.id,
            DatabricksSource.id,
            McpSource.id,
        )
    }
    rendered = frame(BoardState(pane=pane_id), snaps=snaps, cols=120, now=NOW)
    assert rendered.count == 0
    assert rendered.lines[0].startswith("panes ")
