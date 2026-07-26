"""Tests for ``monitorcore.view`` — the integrated drillable frame (WU5), weaving the
group tree + event feed + nav selection + drill + filter + stall marks into one row list.
100% line+branch.
"""

from __future__ import annotations

from monitorcore.codex_tail import CodexThread, ToolEvent
from monitorcore.group_tree import derive_groups
from monitorcore.nav import ViewState
from monitorcore.responsive import Breakpoint, Layout
from monitorcore.view import render_view

_NOW = 1609459200.0


def _th(key: str, label: str, status: str = "idle", *, events: int = 0) -> CodexThread:
    th = CodexThread(key=key, source="stream", path=key, label=label)
    th.status = status
    th.start_ts = _NOW
    th.last_ts = _NOW
    for i in range(events):
        th.add_event(ToolEvent("cmd", "shell", f"step{i}", "ok", None, _NOW))
    return th


def _fleet() -> tuple[CodexThread, ...]:
    return (
        _th("t1", "audit", "running", events=10),
        _th("t2", "audit", "idle"),
        _th("t3", "rescue", "aborted"),
    )


def _groups():
    return derive_groups(_fleet())


def _joined(rows: list[str]) -> str:
    return "\n".join(rows)


# ───────────────────────────── title / selection ─────────────────────────────
def test_title_row_leads_and_is_never_selected() -> None:
    rows = render_view(_groups(), ViewState(), _NOW, 120)
    assert rows[0].startswith("  CODEX COCKPIT")  # gutter, no cursor on the title


def test_default_selection_marks_the_first_nav_item() -> None:
    rows = render_view(_groups(), ViewState(selected=0), _NOW, 120)
    # exactly one row carries the cursor
    cursored = [r for r in rows if r.startswith("> ")]
    assert len(cursored) == 1
    assert "rescue" in cursored[0]  # worst group sorts first, so it is item 0


def test_cursor_can_land_on_a_thread() -> None:
    g = _groups()
    # item 0 = rescue group, item 1 = its thread t3
    rows = render_view(g, ViewState(selected=1), _NOW, 120)
    (cursored,) = [r for r in rows if r.startswith("> ")]
    assert "[ABORTED]" in cursored or "ABORTED" in cursored


def test_selection_clamps_high_and_low() -> None:
    g = _groups()
    high = render_view(g, ViewState(selected=999), _NOW, 120)
    assert len([r for r in high if r.startswith("> ")]) == 1
    low = render_view(g, ViewState(selected=-5), _NOW, 120)
    assert len([r for r in low if r.startswith("> ")]) == 1


def test_empty_fleet_renders_only_the_title() -> None:
    rows = render_view(derive_groups(()), ViewState(), _NOW, 120)
    assert len(rows) == 1
    assert rows[0].startswith("  CODEX COCKPIT")
    assert not any(r.startswith("> ") for r in rows)  # nothing selectable


# ───────────────────────────── cursor off (--once) ─────────────────────────────
def test_cursor_off_shows_no_selection() -> None:
    rows = render_view(_groups(), ViewState(selected=0), _NOW, 120, cursor=False)
    assert not any(r.startswith("> ") for r in rows)


# ───────────────────────────── drill / feed depth ─────────────────────────────
def test_drilled_thread_shows_its_full_feed() -> None:
    g = _groups()
    # t1 (audit/running) has 10 events; at NORMAL width the feed is capped at 3
    drilled = render_view(g, ViewState(drilled="t1"), _NOW, 100)
    steps = [r for r in drilled if "step" in r]
    assert len(steps) == 10  # drill overrides the layout cap → full feed


def test_non_drilled_thread_honours_the_layout_feed_cap() -> None:
    g = _groups()
    rows = render_view(g, ViewState(), _NOW, 100)  # NORMAL → event_limit 3
    t1_steps = [r for r in rows if "step" in r]
    assert len(t1_steps) == 3  # capped, not the full 10


def test_narrow_width_suppresses_the_feed() -> None:
    g = _groups()
    rows = render_view(g, ViewState(), _NOW, 60)  # NARROW → no events
    assert not any("step" in r for r in rows)


# ───────────────────────────── collapse ─────────────────────────────
def test_collapsed_group_hides_its_threads() -> None:
    g = _groups()
    rows = render_view(g, ViewState(collapsed=frozenset({"audit"})), _NOW, 120)
    joined = _joined(rows)
    assert "audit" in joined  # the header is still shown
    assert "[RUNNING]" not in joined  # its member thread lines are gone


# ───────────────────────────── stall marks ─────────────────────────────
def test_stall_mark_is_appended_to_a_thread_line() -> None:
    g = _groups()
    rows = render_view(g, ViewState(), _NOW, 120, marks={"t1": "STALL"})
    assert any("[STALL]" in r for r in rows)


def test_no_marks_leaves_lines_unmarked() -> None:
    g = _groups()
    rows = render_view(g, ViewState(), _NOW, 120)
    assert not any("[STALL]" in r for r in rows)


# ───────────────────────────── filter title ─────────────────────────────
def test_filtering_mode_shows_the_query_prompt() -> None:
    rows = render_view(_groups(), ViewState(filtering=True, query="aud"), _NOW, 120)
    assert "/aud" in rows[0]


def test_active_filter_is_shown_in_the_title() -> None:
    rows = render_view(_groups(), ViewState(query="aud"), _NOW, 120)
    assert "filter: aud" in rows[0]


# ───────────────────────────── explicit layout ─────────────────────────────
def test_explicit_layout_overrides_the_width() -> None:
    forced = Layout(
        breakpoint=Breakpoint.FULL,
        ascii=False,
        problems_only=False,
        show_events=False,
        event_limit=0,
    )
    rows = render_view(_groups(), ViewState(), _NOW, 40, layout=forced)
    # tiny cols but the forced layout keeps rich glyphs and drops events
    assert not any("step" in r for r in rows)
    assert any("▾" in r for r in rows)
