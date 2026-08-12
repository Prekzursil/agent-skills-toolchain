"""``unified`` — ONE cockpit board with SWITCHABLE PANES (the Phase-2 through-line).

Phase 1 shipped a Codex-only cockpit. This module generalises that loop to N panes over N
sources without forking any of it: the Codex pane still renders through the very same
:func:`monitorcore.view.render_view`, and the loop keeps the exact seam set
:func:`monitorcore.cockpit.run_interactive` already uses (``read_key`` / ``write`` /
``clock`` / ``cols_fn``), so the whole board is exercised with injected values and no real
terminal. The raw ``getch``, the real paint and the tty/env probe are IMPORTED from
``cockpit`` rather than re-declared, so this module adds **no new no-cover SHELL** — its only
``# pragma: no cover`` is the standard ``if __name__ == "__main__"`` entrypoint guard that
every module CLI in this package already carries.

The loop is keystroke-driven, deliberately, exactly as Phase 1 is: one keypress = one
``poll_all`` = one repaint. There is no timer and no busy poll.

Keys — ``1``-``6`` jump straight to a pane · ``tab`` cycles · ``↑``/``k`` and ``↓``/``j``
move the selection within the active pane · ``q`` quits.

The loop also owns the WU6 stall layer for the codex pane (:func:`codex_marks`), because the
content-freeze half of that classifier needs a :class:`~monitorcore.stall.StallTracker` that
outlives one frame. Without it the pane would render the Phase-1 view MINUS its
``[STALL]`` / ``[BLOCKED]`` markers — the one inference a fleet monitor exists to surface.

Two safety properties hold for every pane, not just the ones shipped here:

* **One bad source cannot kill the board.** ``poll`` is contractually forbidden to raise, but
  :func:`poll_all` still wraps each call: a rogue adapter becomes an *unreachable* snapshot
  and its pane prints "not measured", while every other pane keeps rendering. A payload with
  wrong-TYPED rows degrades the same way (:func:`monitorcore.pane.payload_rows`).
* **Nothing untrusted reaches the terminal un-stripped.** Every row leaves a pane through
  :func:`monitorcore.pane.cursor_rows` → :func:`monitorcore.codex_tail.clip`, and the
  header/badge are clipped here, so a hostile agent name / workflow label / MCP server name
  cannot emit an escape byte into the painted frame. The badge additionally REDACTS
  (:func:`monitorcore.pane.safe`), because adapters keep ``Snapshot.error`` raw for logs and
  this board is where that string becomes pixels.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from .agents_source import AgentsSource
from .codex_source import CodexSource
from .codex_tail import CodexThread, clip
from .cockpit import _default_write, _getch, _mtime, _supported, stall_marks
from .contract import MonitorSource, Snapshot, SourceState
from .databricks_source import DatabricksSource
from .health_source import SystemHealthSource
from .mcp_source import McpSource
from .pane import (
    GUTTER,
    Pane,
    PaneCtx,
    PaneId,
    clamp,
    pane_bar,
    payload_rows,
    safe,
    state_badge,
)
from .pane_views import PANES
from .stall import StallTracker

__all__ = [
    "BoardFrame",
    "BoardState",
    "active_pane",
    "apply_key",
    "codex_marks",
    "default_sources",
    "frame",
    "main",
    "poll_all",
    "run_board",
]

_QUIT_KEYS = ("q", "quit")
_NEXT_KEYS = ("\t", "tab")
_UP_KEYS = ("up", "k")
_DOWN_KEYS = ("down", "j")

_GUTTER_LEN = len(GUTTER)


@dataclass(frozen=True)
class BoardState:
    """The immutable board state: which pane is active, where the cursor is, and quit."""

    pane: str = PaneId.CODEX
    selected: int = 0
    quit: bool = False


@dataclass(frozen=True)
class BoardFrame:
    """One rendered board: the ANSI-free rows plus the active pane's selectable-row count."""

    lines: tuple[str, ...] = ()
    count: int = 0


def active_pane(panes: Sequence[Pane], pane_id: str) -> Pane:
    """The pane matching ``pane_id``, falling back to the FIRST pane on an unknown id."""
    for pane in panes:
        if pane.id == pane_id:
            return pane
    return panes[0]


def poll_all(
    sources: Mapping[str, MonitorSource[Any]],
    *,
    clock: Callable[[], float] = time.time,
) -> dict[str, Snapshot[Any]]:
    """Poll every registered source once, keyed by ``source_id``.

    ``poll`` MUST NOT raise (the contract's cardinal rule), but a THIRD-PARTY adapter is not
    bound by our tests, so a raise here is converted into an unreachable snapshot with a
    ``None`` payload. The pane then prints "not measured" instead of the board dying.
    """
    out: dict[str, Snapshot[Any]] = {}
    for source_id, source in sources.items():
        try:
            out[source_id] = source.poll()
        except Exception as exc:
            text = safe(str(exc))
            out[source_id] = Snapshot(
                source_id=source_id,
                ts=clock(),
                reachable=False,
                stale=True,
                state=SourceState.UNREACHABLE,
                headline=f"{safe(source_id)} [unreachable] {text}",
                payload=None,
                age_s=None,
                error=text,
            )
    return out


def codex_marks(
    snaps: Mapping[str, Snapshot[Any]],
    tracker: StallTracker,
    now: float,
    *,
    stale_s: float,
    mtime_fn: Callable[[str], float | None] = _mtime,
) -> dict[str, str]:
    """The WU6 ``STALL`` / ``BLOCKED`` markers for the codex snapshot in ``snaps``.

    The board, not the pane, owns this: a content freeze needs TWO polls to corroborate, so
    the :class:`~monitorcore.stall.StallTracker` has to outlive a single frame. This is the
    SAME :func:`monitorcore.cockpit.stall_marks` classifier the Phase-1 cockpit loop drives
    — re-derived markers would be a second, drifting stall policy.
    """
    threads = payload_rows(snaps.get(CodexSource.id), "threads", of=CodexThread)
    return stall_marks(tracker, threads, now, stale_s=stale_s, mtime_fn=mtime_fn)


def frame(
    state: BoardState,
    *,
    snaps: Mapping[str, Snapshot[Any]],
    panes: Sequence[Pane] = PANES,
    cols: int = 120,
    now: float = 0.0,
    cursor: bool = True,
    marks: Mapping[str, str] | None = None,
) -> BoardFrame:
    """Compose the whole board: the tab strip, the source badge, then the active pane's rows.

    ``marks`` is the codex stall/blocked overlay (see :func:`codex_marks`); it is ``None``
    for a single read-only frame, because one snapshot cannot corroborate a freeze — the
    rule :func:`monitorcore.cockpit.once_frame` already states for the Phase-1 board.
    """
    pane = active_pane(panes, state.pane)
    snap = snaps.get(pane.source_id)
    ctx = PaneCtx(
        cols=cols,
        now=now,
        selected=state.selected,
        cursor=cursor,
        marks=marks if marks is not None else {},
    )
    body = pane.body(snap, ctx)
    badge = clip(
        state_badge(snap, source_id=pane.source_id), max(0, cols - _GUTTER_LEN)
    )
    header = (pane_bar(panes, pane.id, cols), GUTTER + badge)
    return BoardFrame(header + body.lines, body.count)


def _index(ids: Sequence[str], pane_id: str) -> int:
    """The active pane's position, or ``0`` when the id is unknown (never raises)."""
    if pane_id in ids:
        return ids.index(pane_id)
    return 0


def _switch(state: BoardState, pane_id: str) -> BoardState:
    """Activate ``pane_id`` and reset the cursor (row N of one pane means nothing in another)."""
    return replace(state, pane=pane_id, selected=0)


def _digit_pane(ids: Sequence[str], key: str) -> str | None:
    """The pane a ``1``-``9`` key selects, or ``None`` when the key is not an in-range digit."""
    if len(key) != 1 or not key.isdigit():
        return None
    idx = int(key) - 1
    if 0 <= idx < len(ids):
        return ids[idx]
    return None


def apply_key(
    state: BoardState,
    key: str,
    *,
    panes: Sequence[Pane] = PANES,
    count: int = 0,
) -> BoardState:
    """The single pure transition: fold one keystroke into the board state.

    ``count`` is the selectable-row count of the frame the user is looking at, so the cursor
    is clamped against what is actually on screen.
    """
    ids = tuple(pane.id for pane in panes)
    if key in _QUIT_KEYS:
        return replace(state, quit=True)
    if key in _NEXT_KEYS:
        return _switch(state, ids[(_index(ids, state.pane) + 1) % len(ids)])
    target = _digit_pane(ids, key)
    if target is not None:
        return _switch(state, target)
    if key in _UP_KEYS:
        return replace(state, selected=clamp(state.selected - 1, count))
    if key in _DOWN_KEYS:
        return replace(state, selected=clamp(state.selected + 1, count))
    return state


def run_board(
    sources: Mapping[str, MonitorSource[Any]],
    *,
    panes: Sequence[Pane] = PANES,
    read_key: Callable[[], str] = _getch,
    write: Callable[[Sequence[str]], None] = _default_write,
    clock: Callable[[], float] = time.time,
    cols_fn: Callable[[], int] = lambda: 120,
    initial: BoardState | None = None,
    tracker: StallTracker | None = None,
    mtime_fn: Callable[[str], float | None] = _mtime,
    stale_s: float = 90.0,
) -> BoardState:
    """The keystroke-driven multi-pane loop: poll → render → read a key → apply → repeat.

    Blocks on ``read_key`` (a keystroke drives each repaint — no busy poll), the same
    contract :func:`monitorcore.cockpit.run_interactive` established. Returns the final
    :class:`BoardState` when the user quits.

    The loop owns ONE :class:`~monitorcore.stall.StallTracker` for its whole lifetime — the
    cross-poll half of WU6's two-signal stall classifier only corroborates from the second
    poll onward, so a per-frame tracker would never fire. ``mtime_fn`` and ``stale_s`` are
    the same injected seams :func:`monitorcore.cockpit.run_interactive` exposes.
    """
    state = initial if initial is not None else BoardState()
    tracker = tracker if tracker is not None else StallTracker()
    while True:
        now = clock()
        snaps = poll_all(sources, clock=clock)
        marks = codex_marks(snaps, tracker, now, stale_s=stale_s, mtime_fn=mtime_fn)
        rendered = frame(
            state, snaps=snaps, panes=panes, cols=cols_fn(), now=now, marks=marks
        )
        write(rendered.lines)
        state = apply_key(state, read_key(), panes=panes, count=rendered.count)
        if state.quit:
            return state


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Unified monitor cockpit — ONE board, switchable panes "
        "(codex · agents · workflows · databricks · mcp · health). --once renders a single "
        "read-only frame and degrades cleanly under Windows Terminal."
    )
    ap.add_argument(
        "--pane",
        default=PaneId.CODEX.value,
        choices=[p.value for p in PaneId],
        help="the pane to open on (or to render with --once)",
    )
    ap.add_argument("--width", type=int, default=120, help="board width in columns")
    ap.add_argument(
        "--once", action="store_true", help="render a single read-only frame and exit"
    )
    ap.add_argument("--stream-dir", default=None, help="codex exec --json stream dir")
    ap.add_argument("--sessions-dir", default=None, help="codex rollout sessions dir")
    ap.add_argument("--subagents-dir", default=None, help="claude subagents dir")
    ap.add_argument(
        "--events-path", default=None, help="databricks NDJSON event stream"
    )
    ap.add_argument(
        "--mcp-config",
        action="append",
        default=None,
        help="an MCP config document to read (repeatable; default: the standard scopes)",
    )
    ap.add_argument(
        "--health-path", default=None, help="system-sentinel NDJSON event log"
    )
    return ap


def default_sources(
    args: argparse.Namespace, *, clock: Callable[[], float] = time.time
) -> dict[str, MonitorSource[Any]]:
    """Construct one adapter per registered source (constructors do NO I/O — polling does)."""
    return {
        CodexSource.id: CodexSource(
            stream_dir=args.stream_dir, sessions_dir=args.sessions_dir, clock=clock
        ),
        AgentsSource.id: AgentsSource(subdir=args.subagents_dir, clock=clock),
        DatabricksSource.id: DatabricksSource(
            events_path=args.events_path, clock=clock
        ),
        McpSource.id: McpSource(paths=args.mcp_config, clock=clock),
        # No ``clock=``: this adapter deliberately takes none. Its freshness is derived from
        # the SAMPLE's own timestamp against wall time, which is what makes the dead-man rule
        # work — a source that read the board's injected clock could be handed a frozen clock
        # and would then never age its feed out.
        SystemHealthSource.id: SystemHealthSource(events_path=args.health_path),
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    sources: Mapping[str, MonitorSource[Any]] | None = None,
    panes: Sequence[Pane] = PANES,
    out: Callable[[str], None] = print,
    clock: Callable[[], float] = time.time,
    board: Callable[..., BoardState] = run_board,
    supported_fn: Callable[[], bool] = _supported,
) -> int:
    """CLI. ``--once`` (or a non-interactive terminal) prints ONE read-only frame of
    ``--pane``; otherwise it hands off to the switchable-pane loop. Every seam is injected,
    so both lanes AND the degradation path are covered without a terminal.
    """
    args = _build_parser().parse_args(argv)
    srcs = sources if sources is not None else default_sources(args, clock=clock)
    state = BoardState(pane=args.pane)
    if args.once or not supported_fn():
        # No ``marks=``: one snapshot cannot corroborate a content freeze, so ``--once``
        # shows fact-level state only — the identical rule ``cockpit.once_frame`` follows.
        rendered = frame(
            state,
            snaps=poll_all(srcs, clock=clock),
            panes=panes,
            cols=args.width,
            now=clock(),
            cursor=False,
        )
        for line in rendered.lines:
            out(line)
        return 0
    board(
        srcs,
        panes=panes,
        cols_fn=lambda: args.width,
        clock=clock,
        initial=state,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- module CLI entrypoint
    raise SystemExit(main())
