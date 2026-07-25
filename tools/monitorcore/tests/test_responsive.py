"""Tests for ``monitorcore.responsive`` — the four responsive-width breakpoints and the
top-level board renderer (WU4), incl. the ``<50-col`` problems-only mode, 100%
line+branch.
"""

from __future__ import annotations

import pytest

from monitorcore.codex_tail import CodexThread, ToolEvent
from monitorcore.group_tree import derive_groups
from monitorcore.responsive import (
    Breakpoint,
    Layout,
    board_title,
    breakpoint_for,
    layout_for,
    render_board,
)

_NOW = 1609459200.0


def _th(
    *,
    key: str,
    label: str = "",
    source: str = "stream",
    status: str = "idle",
) -> CodexThread:
    th = CodexThread(key=key, source=source, path=key, label=label)
    th.status = status
    th.start_ts = _NOW
    th.last_ts = _NOW
    return th


# ───────────────────────────── breakpoint_for ─────────────────────────────
@pytest.mark.parametrize(
    ("cols", "expected"),
    [
        (10, Breakpoint.MINI),
        (49, Breakpoint.MINI),  # just below the mini ceiling
        (50, Breakpoint.NARROW),  # boundary → narrow
        (79, Breakpoint.NARROW),
        (80, Breakpoint.NORMAL),  # boundary → normal
        (119, Breakpoint.NORMAL),
        (120, Breakpoint.FULL),  # boundary → full
        (240, Breakpoint.FULL),
    ],
)
def test_breakpoint_for(cols: int, expected: Breakpoint) -> None:
    assert breakpoint_for(cols) is expected


# ───────────────────────────── layout_for ─────────────────────────────
def test_layout_for_mini_is_ascii_problems_only_no_events() -> None:
    lay = layout_for(40)
    assert lay.breakpoint is Breakpoint.MINI
    assert (lay.ascii, lay.problems_only, lay.show_events, lay.event_limit) == (
        True,
        True,
        False,
        0,
    )


def test_layout_for_narrow_is_ascii_all_no_events() -> None:
    lay = layout_for(60)
    assert lay.breakpoint is Breakpoint.NARROW
    assert (lay.ascii, lay.problems_only, lay.show_events, lay.event_limit) == (
        True,
        False,
        False,
        0,
    )


def test_layout_for_normal_shows_a_short_feed() -> None:
    lay = layout_for(100)
    assert lay.breakpoint is Breakpoint.NORMAL
    assert (lay.ascii, lay.problems_only, lay.show_events, lay.event_limit) == (
        False,
        False,
        True,
        3,
    )


def test_layout_for_full_shows_a_long_feed() -> None:
    lay = layout_for(150)
    assert lay.breakpoint is Breakpoint.FULL
    assert (lay.ascii, lay.problems_only, lay.show_events, lay.event_limit) == (
        False,
        False,
        True,
        8,
    )


# ───────────────────────────── board_title ─────────────────────────────
def test_board_title_counts_groups_and_threads() -> None:
    groups = derive_groups(
        [
            _th(key="t1", label="audit", status="running"),
            _th(key="t2", label="audit", status="idle"),
            _th(key="t3", label="rescue", status="aborted"),
        ]
    )
    assert board_title(groups) == "CODEX COCKPIT · 2 groups · 3 threads"


# ───────────────────────────── render_board ─────────────────────────────
def _fleet() -> tuple[CodexThread, ...]:
    clean = _th(key="c1", label="audit", status="running")
    clean.add_event(ToolEvent("tool", "shell", "pytest -q", "ok", None, _NOW))
    problem = _th(key="p1", label="rescue", status="aborted")
    return (clean, _th(key="c2", label="audit", status="idle"), problem)


def test_render_board_full_shows_rich_tree_with_feed() -> None:
    groups = derive_groups(_fleet())
    rows = render_board(groups, _NOW, 120)
    assert rows[0] == "CODEX COCKPIT · 2 groups · 3 threads"
    joined = "\n".join(rows)
    assert "▾ audit R●1 I○1 D✓0 X✘0" in joined  # rich rollup header
    assert "▾ rescue R●0 I○0 D✓0 X✘1" in joined
    assert "shell: pytest -q" in joined  # event feed interleaved


def test_render_board_narrow_is_ascii_and_dropped_feed() -> None:
    groups = derive_groups(_fleet())
    rows = render_board(groups, _NOW, 60)
    joined = "\n".join(rows)
    assert "v audit R1 I1 D0 X0" in joined  # ascii marker + ascii rollup
    assert "shell: pytest -q" not in joined  # feed suppressed at narrow width


def test_render_board_mini_is_problems_only() -> None:
    groups = derive_groups(_fleet())
    rows = render_board(groups, _NOW, 40)
    joined = "\n".join(rows)
    # the aborted "rescue" group is shown; the healthy "audit" group is dropped
    assert "v rescue R0 I0 D0 X1" in joined
    assert "audit" not in joined
    assert "shell: pytest -q" not in joined


def test_render_board_explicit_layout_overrides_the_width() -> None:
    groups = derive_groups(_fleet())
    forced = Layout(
        breakpoint=Breakpoint.FULL,
        ascii=False,
        problems_only=False,
        show_events=False,
        event_limit=0,
    )
    rows = render_board(groups, _NOW, 40, layout=forced)  # tiny cols, but layout wins
    joined = "\n".join(rows)
    assert "▾ audit" in joined  # healthy group present despite <50 cols
    assert "shell: pytest -q" not in joined  # events off per the forced layout
