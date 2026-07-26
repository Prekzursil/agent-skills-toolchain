"""``view`` — weave the group tree + event feed + nav state into ONE drillable frame (WU5).

The single integrated renderer: it takes the derived group tree (WU3), a
:class:`~monitorcore.nav.ViewState`, and an optional per-thread stall/blocked ``marks`` map
(WU6), and produces the ANSI-free logical rows the cockpit frames. It composes the existing
primitives — :func:`monitorcore.group_tree.group_header`,
:func:`monitorcore.codex_tail.board_line`, :func:`monitorcore.event_feed.event_rows`, and
the :func:`monitorcore.responsive.layout_for` breakpoint policy — and layers the
interaction on top:

* the query FILTER (via :func:`monitorcore.nav.visible_groups`) and the collapse set,
* a one-column SELECTION cursor (``> ``) on the selected nav item's header row (a plain
  two-space gutter on every other row, so columns stay aligned),
* DRILL: the drilled thread shows its FULL event feed regardless of the width cap,
* stall/blocked MARKS appended to a thread's line (``[STALL]`` / ``[BLOCKED]``) — never
  colour here; colour policy lives in :mod:`monitorcore.stall`.

Pure over the injected group tree / state / width (no I/O, no clock), so it reaches 100%
line+branch under injected inputs and vendors cleanly into a skill's plain Python.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .codex_tail import CodexThread, board_line, clip
from .event_feed import event_rows
from .group_tree import Group, group_header
from .nav import ViewState, nav_items, visible_groups
from .responsive import Layout, board_title, layout_for

__all__ = ["render_view"]

_CURSOR = "> "  # selection marker (width 2, aligns with the plain gutter)
_GUTTER = "  "
_GUTTER_LEN = len(_GUTTER)
_THREAD_INDENT = "  "  # a thread sits under its group header
_EVENT_INDENT = "    "  # an event sits under its thread line
_THREAD_INDENT_LEN = len(_THREAD_INDENT)


def render_view(
    groups: Sequence[Group],
    state: ViewState,
    now: float,
    cols: int,
    *,
    marks: Mapping[str, str] | None = None,
    cursor: bool = True,
    layout: Layout | None = None,
) -> list[str]:
    """The full drillable frame as ANSI-free rows: title, then each visible group block.

    ``marks`` maps a thread key to a short condition marker (WU6); ``cursor`` draws the
    selection marker (off for the read-only ``--once`` frame); ``layout`` forces a
    breakpoint (else derived from ``cols``).
    """
    marks = marks or {}
    lay = layout_for(cols) if layout is None else layout
    inner = max(0, cols - _GUTTER_LEN)
    vgroups = visible_groups(groups, state)
    items = nav_items(vgroups)
    sel = _sel_index(state, len(items))

    rows = [_row(_title(vgroups, state, inner), selected=False)]
    idx = 0
    for group in vgroups:
        header = clip(group_header(group, ascii=lay.ascii), inner)
        rows.append(_row(header, selected=cursor and idx == sel))
        idx += 1
        if group.collapsed:
            continue
        for thread in group.threads:
            rows.extend(
                _thread_block(
                    thread,
                    now,
                    inner,
                    lay,
                    marks,
                    state,
                    selected=cursor and idx == sel,
                )
            )
            idx += 1
    return rows


def _sel_index(state: ViewState, count: int) -> int:
    """The clamped selected index, or ``-1`` when there is nothing selectable."""
    if count == 0:
        return -1
    if state.selected < 0:
        return 0
    if state.selected >= count:
        return count - 1
    return state.selected


def _title(vgroups: Sequence[Group], state: ViewState, inner: int) -> str:
    """The board title, carrying the live filter prompt / active-filter fragment."""
    base = board_title(vgroups)
    if state.filtering:
        text = f"{base}  /{state.query}"
    elif state.query:
        text = f"{base}  filter: {state.query}"
    else:
        text = base
    return clip(text, inner)


def _thread_block(
    thread: CodexThread,
    now: float,
    inner: int,
    layout: Layout,
    marks: Mapping[str, str],
    state: ViewState,
    *,
    selected: bool,
) -> list[str]:
    """A thread's board line (with any mark), then — when expanded — its event feed.

    The drilled thread shows its FULL feed (limit ``None``); an undrilled thread shows the
    layout's capped feed only when the breakpoint enables events.
    """
    line = board_line(thread, now)
    mark = marks.get(thread.key, "")
    if mark:
        line = f"{line}  [{mark}]"
    body = _THREAD_INDENT + clip(line, max(0, inner - _THREAD_INDENT_LEN))
    rows = [_row(body, selected=selected)]
    drilled = state.drilled == thread.key
    if drilled or layout.show_events:
        limit = None if drilled else layout.event_limit
        rows.extend(
            _row(event_row, selected=False)
            for event_row in event_rows(
                thread.events, inner, limit=limit, indent=_EVENT_INDENT
            )
        )
    return rows


def _row(content: str, *, selected: bool) -> str:
    """Prefix ``content`` with the selection cursor or the plain gutter."""
    return (_CURSOR if selected else _GUTTER) + content
