"""``responsive`` — the responsive-width breakpoints + the top-level board renderer (WU4).

Picks how much of the ``fleet → group → thread → event`` tree to draw for the terminal's
current column count, then assembles the board rows by composing the group tree (WU3) and
the event feed (WU2). PURE over the already-derived :class:`~monitorcore.group_tree.Group`
tuple and an injected width — no I/O, no clock, no terminal read — so it reaches 100%
line+branch under injected inputs and the caller owns querying the real terminal size.

Four breakpoints, widest to narrowest:

* ``FULL`` (``>= 120``) — rich glyphs, every group + thread, a long event feed.
* ``NORMAL`` (``80..119``) — rich glyphs, every group + thread, a short event feed.
* ``NARROW`` (``50..79``) — ASCII fallback glyphs, every group + thread, feed suppressed.
* ``MINI`` (``< 50``) — the ``<50-col`` **problems-only** mode: ASCII glyphs, feed
  suppressed, and only groups with a corroborated failure are drawn (and within them only
  the failing threads), while each drawn header's rollup still counts every member so the
  triage totals stay honest.

The board never gates execution (propose-not-dispose) and none of this can raise on a
valid group tree, so it degrades a display, never the monitored work. The module is
stdlib-only so it vendors cleanly into a skill's plain Python.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from .codex_tail import CodexThread, clip
from .group_tree import Group, group_rows, is_problem

__all__ = [
    "Breakpoint",
    "Layout",
    "board_title",
    "breakpoint_for",
    "layout_for",
    "render_board",
]


class Breakpoint(StrEnum):
    """The coarse width class of the terminal (a ``str`` at runtime)."""

    MINI = "mini"  # < 50 cols — problems-only
    NARROW = "narrow"  # 50..79 cols
    NORMAL = "normal"  # 80..119 cols
    FULL = "full"  # >= 120 cols


@dataclass(frozen=True)
class Layout:
    """The render policy for a breakpoint: glyph mode, triage filter, and feed depth."""

    breakpoint: Breakpoint
    ascii: bool
    problems_only: bool
    show_events: bool
    event_limit: int


_MINI_MAX = 50  # below this → MINI (problems-only)
_NARROW_MAX = 80  # below this → NARROW
_NORMAL_MAX = 120  # below this → NORMAL; at/above → FULL


def breakpoint_for(cols: int) -> Breakpoint:
    """The :class:`Breakpoint` for a terminal ``cols`` width."""
    if cols < _MINI_MAX:
        return Breakpoint.MINI
    if cols < _NARROW_MAX:
        return Breakpoint.NARROW
    if cols < _NORMAL_MAX:
        return Breakpoint.NORMAL
    return Breakpoint.FULL


_LAYOUTS = {
    Breakpoint.MINI: Layout(
        breakpoint=Breakpoint.MINI,
        ascii=True,
        problems_only=True,
        show_events=False,
        event_limit=0,
    ),
    Breakpoint.NARROW: Layout(
        breakpoint=Breakpoint.NARROW,
        ascii=True,
        problems_only=False,
        show_events=False,
        event_limit=0,
    ),
    Breakpoint.NORMAL: Layout(
        breakpoint=Breakpoint.NORMAL,
        ascii=False,
        problems_only=False,
        show_events=True,
        event_limit=3,
    ),
    Breakpoint.FULL: Layout(
        breakpoint=Breakpoint.FULL,
        ascii=False,
        problems_only=False,
        show_events=True,
        event_limit=8,
    ),
}


def layout_for(cols: int) -> Layout:
    """The :class:`Layout` policy for a terminal ``cols`` width."""
    return _LAYOUTS[breakpoint_for(cols)]


def board_title(groups: Iterable[Group]) -> str:
    """The board title line: ``CODEX COCKPIT · <n> groups · <m> threads``."""
    groups = tuple(groups)
    threads = sum(len(g.threads) for g in groups)
    return f"CODEX COCKPIT · {len(groups)} groups · {threads} threads"


def _group_block(group: Group, now: float, cols: int, layout: Layout) -> list[str]:
    """One group's rows under ``layout`` (``[]`` when problems-only and it is healthy)."""
    threads: tuple[CodexThread, ...] | None
    if layout.problems_only:
        threads = tuple(th for th in group.threads if is_problem(th))
        if not threads:
            return []
    else:
        threads = None
    return group_rows(
        group,
        now,
        cols,
        threads=threads,
        ascii=layout.ascii,
        show_events=layout.show_events,
        event_limit=layout.event_limit,
    )


def render_board(
    groups: Iterable[Group],
    now: float,
    cols: int,
    *,
    layout: Layout | None = None,
) -> list[str]:
    """The full board as ANSI-free rows: title, then each group's block.

    ``layout`` defaults to :func:`layout_for` (``cols``); pass an explicit one to force a
    breakpoint (e.g. a ``--once`` export at a fixed width). The rows are logical and
    width-clipped; the caller frames them via :func:`monitorcore.board.assemble_frame`.
    """
    groups = tuple(groups)
    lay = layout_for(cols) if layout is None else layout
    rows = [clip(board_title(groups), cols)]
    for group in groups:
        rows.extend(_group_block(group, now, cols, lay))
    return rows
